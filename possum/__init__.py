#!/usr/bin/env python

import argparse
import errno
import hashlib
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError, NoCredentialsError
import docker
from docker.errors import APIError, ImageNotFound
from ruamel.yaml import scanner, YAML

__title__ = 'possum'
__version__ = '1.4.4'
__author__ = 'Bryson Tyrrell'
__author_email__ = 'bryson.tyrrell@gmail.com'
__license__ = 'MIT'
__copyright__ = 'Copyright 2018 Bryson Tyrrell'

WORKING_DIR = os.getcwd()
USER_DIR = os.path.expanduser('~')
POSSUM_PATH = ''
PIPENV_PATH = shutil.which('pipenv')
S3_BUCKET_NAME = ''
S3_ARTIFACT_DIR = ''

logger = logging.getLogger(__name__)


class MyFormatter(logging.Formatter):
    """This is a custom formatter for the logger to write INFO level messages
    without showing the level. All other levels display the level.

    Example output::

        >>> logger.info('A message')
        'A message'
        >>> logger.error('A message')
        'ERROR: A Message'

    """
    info_format = "%(message)s"
    error_warn_format = "%(levelname)s: %(message)s"

    def __init__(self):
        super().__init__(fmt="%(levelno)d: %(msg)s", datefmt=None, style='%')

    def format(self, record):
        original_format = self._style._fmt

        if record.levelno != logging.INFO:
            self._style._fmt = MyFormatter.error_warn_format

        elif record.levelno == logging.INFO:
            self._style._fmt = MyFormatter.info_format

        result = logging.Formatter.format(self, record)
        self._style._fmt = original_format
        return result


def configure_logger():
    """Configure the logger. For use when invoked as a CLI tool."""
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(MyFormatter())
    stream_handler.setLevel(logging.DEBUG)

    logger.addHandler(stream_handler)
    logger.setLevel(logging.INFO)


def arguments():
    """Parse command line arguments when invoked as a CLI tool.

    :returns: Parsed arguments
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        'possum',
        description='Possum is a utility to package Python-based serverless '
                    'applications using the Amazon Serverless Application '
                    'model with per-function dependencies.'
    )

    parser.add_argument(
        's3_bucket',
        help="The S3 bucket to upload artifacts. You may optionally pass a "
             "path within the bucket to store the Lambda artifacts (defaults "
             "to 'possum-{timestamp}').",
        type=str,
        metavar='s3_bucket'
    )

    parser.add_argument(
        '-t', '--template',
        help='The filename of the SAM template.',
        type=str,
        default='template.yaml',
        metavar='template'
    )

    parser.add_argument(
        '-o', '--output-template',
        help='Optional filename for the output template.',
        type=str,
        metavar='output'
    )

    parser.add_argument(
        '-p', '--profile',
        help='Optional profile name for AWS credentials.',
        type=str,
        metavar='profile_name'
    )

    parser.add_argument(
        '-c', '--clean',
        help='Build all Lambda packages, ignoring previous run.',
        action='store_true'
    )

    parser.add_argument(
        '--docker',
        help='Build Lambda packages within a Docker container environment.',
        action='store_true'
    )

    parser.add_argument(
        '--docker-image',
        help="Specify a Docker image to use (defaults to 'possum:latest').",
        type=str,
        default='possum:latest',
        metavar='image_name'
    )

    parser.add_argument(
        '-v', '--version',
        help='Display version information.',
        action='version',
        version=f'Possum {__version__}'
    )

    return parser.parse_args()


def possum_name():
    return f'{os.path.split(WORKING_DIR)[-1]}-' \
           f'{hashlib.sha1(WORKING_DIR.encode()).hexdigest()[-8:]}'


def get_possum_path():
    possum_dir = os.path.join(USER_DIR, '.possum')
    if not os.path.exists(possum_dir):
        logger.info('Creating Possum directory...')
        os.mkdir(possum_dir)
    elif not os.path.isdir(possum_dir):
        logger.error(f"'{possum_dir}' is not a directory! Delete to "
                     "allow Possum to recreate the directory")
        sys.exit(1)

    return os.path.join(possum_dir, possum_name())


def hash_directory(path):
    """Recursively hashes the contents of a directory and returns the hex value.

    :param path: The path to the directory

    :return: SHA1 hash
    :rtype: str
    """
    dir_hash = hashlib.sha1()

    for root, dirs, files in os.walk(path):
        for names in files:
            file_path = os.path.join(root, names)
            if os.path.isfile(file_path):
                with open(file_path, 'rb') as f_obj:
                    while True:
                        buf = f_obj.read(1024 * 1024)
                        if not buf:
                            break
                        dir_hash.update(buf)

    return dir_hash.hexdigest()


class PossumFile(object):
    def __init__(self):
        try:
            with open(POSSUM_PATH, 'r') as f_obj:
                data = YAML().load(f_obj)
        except FileNotFoundError:
            data = {
                'lastRun': dict(),
                's3Uris': dict()
            }

        self._data = data

    def save(self):
        with open(POSSUM_PATH, 'w') as f_obj:
            YAML().dump(self._data, f_obj)

    def check_hash(self, func_name, source_dir):
        last_hash = self._data['lastRun'].get(func_name)
        source_hash = hash_directory(source_dir)

        if last_hash == source_hash:
            return True
        else:
            self._data['lastRun'][func_name] = source_hash
            return False

    def get_last_s3_uri(self, func_name):
        s3_uri = self._data['s3Uris'].get(func_name)
        return s3_uri

    def set_s3_uri(self, func_name, s3_uri):
        self._data['s3Uris'][func_name] = s3_uri


def create_virtual_environment():
    p = subprocess.Popen(
        [
            PIPENV_PATH,
            '--three'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    p.communicate()


def get_virtual_environment_path():
    p = subprocess.Popen(
        [
            PIPENV_PATH,
            '--venv'
        ],
        stdout=subprocess.PIPE
    )
    result = p.communicate()
    return result[0].decode('ascii').strip('\n')


def get_existing_site_packages(venv_path):
    # This can't be hard coded - will fail non-Python 3.6 deployments
    path = os.path.join(venv_path, 'lib/python3.6/site-packages')
    return os.listdir(path)


def install_packages():
    p = subprocess.Popen(
        [
            PIPENV_PATH,
            'install'
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    p.communicate()


def _copy(src, dst):
    try:
        shutil.copytree(src, dst)
    except OSError as exc:
        if exc.errno == errno.ENOTDIR:
            shutil.copy(src, dst)
        else:
            raise


def copy_installed_packages(venv_path, exclusions):
    path = os.path.join(venv_path, 'lib/python3.6/site-packages')
    packages = [i for i in os.listdir(path) if i not in exclusions]
    for package in packages:
        _copy(os.path.join(path, package), os.path.join(os.getcwd(), package))


def create_deployment_package(build_dir, artifact_directory):
    archive_name = uuid.uuid4().hex
    shutil.make_archive(
        archive_name,
        'zip',
        root_dir=build_dir,
        base_dir='./'
    )

    shutil.move(archive_name + '.zip', artifact_directory)
    return archive_name + '.zip'


def remove_virtualenv():
    p = subprocess.Popen(
        [
            PIPENV_PATH,
            '--rm'
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    p.communicate()


def update_template_resource(template, resource, resource_param='CodeUri',
                             s3_object=None, s3_uri=None):
    if s3_object:
        s3_uri = f's3://{S3_BUCKET_NAME}/{S3_ARTIFACT_DIR}/{s3_object}'

    template['Resources'][resource]['Properties'][resource_param] = s3_uri


def upload_artifacts(artifact_directory, profile_name=None):
    session = boto3.Session(profile_name=profile_name)
    s3_client = session.resource('s3')

    os.chdir(artifact_directory)
    logger.info(f'Uploading all Lambda build artifacts to: {S3_ARTIFACT_DIR}')

    for artifact in os.listdir('.'):
        logger.info(f'Uploading artifact: {artifact}')
        try:
            s3_client.Bucket(S3_BUCKET_NAME).upload_file(
                artifact, os.path.join(S3_ARTIFACT_DIR, artifact))
        except NoCredentialsError:
            logger.error('Unable to upload artifacts to the S3 bucket. Boto3 '
                         'was unable to locate credentials!')
            sys.exit(1)
        except (S3UploadFailedError, ClientError)as err:
            logger.error('Failed to upload the artifact to the S3 bucket! '
                         f'Encountered:\n{err}')
            sys.exit(1)


def run_in_docker(image_name):
    command = sys.argv

    command[0] = 'possum'
    command.pop(command.index('--docker'))

    try:
        command.pop(command.index('--docker-image') + 1)
        command.pop(command.index('--docker-image'))
    except ValueError:
        pass

    docker_directory = tempfile.mkdtemp(suffix='-docker', prefix='possum-', dir='/tmp')
    logger.info(f'Working Docker directory: {docker_directory}')

    client = docker.from_env()

    # Copy invocation environment parameters into Docker for use-cases where
    # AWS credentials are not available via the ~/.aws directory.
    container_env = {
        k: v
        for k, v in os.environ.items()
        if k in [
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_SESSION_TOKEN',
        ]
    }

    logger.info('Running Docker container...')

    try:
        container = client.containers.create(
            image=image_name,
            command=command,
            environment=container_env,
            volumes={
                os.path.join(USER_DIR, '.aws'): {
                    'bind': '/root/.aws',
                    'mode': 'ro'
                },
                os.path.dirname(POSSUM_PATH): {
                    'bind': '/root/.possum',
                    'mode': 'rw'
                },
                WORKING_DIR: {
                    'bind': '/task',
                    'mode': 'rw'
                },
                docker_directory: {
                    'bind': '/tmp',
                    'mode': 'rw'
                }
            },
            detach=True
        )
    except ImageNotFound:
        logger.error(f"The Docker image '{image_name}' could not be found")
        sys.exit(1)

    try:
        container.start()
    except APIError as err:
        logger.error(f'Unable to start the Docker container: {err.explanation}')
        sys.exit(1)

    for event in container.logs(stream=True):
        logger.info(event.decode().strip())
        time.sleep(.01)

    container.remove()


def get_s3_bucket_and_dir(bucket_arg):
    """Return the name of the S3 bucket and path to upload Lambda artifacts
    to. If no additional path is provided a default value will be used.

    Bucket Only: ``my-bucket``
    Bucket with Path: ``my-bucket/my-path``

    :param str bucket_arg: The string passed for the ``s3_bucket`` argument.

    :returns Tuple containing the bucket name and path
    :rtype: tuple
    """
    try:
        bucket, dir_ = bucket_arg.split('/', 1)
    except ValueError:
        bucket = bucket_arg
        dir_ = f'possum-{int(time.time())}'

    return bucket, dir_


def get_global(template, resource_type, key):
    """Return a value from the Globals section of a SAM template.

    :param template: The template object
    :param resource_type: The resource type being referenced from the Globals section
    :param key: The key under the resource to return a value from
    """

    template_globals = template.get('Globals')
    if not template_globals:
        return None

    resource = template_globals.get(resource_type)
    if not resource:
        return None

    return resource.get(key)


def main():
    args = arguments()
    configure_logger()

    global POSSUM_PATH
    POSSUM_PATH = get_possum_path()

    if args.docker:
        if not args.docker_image:
            logger.error('A Docker image must be specified')
            sys.exit(1)

        run_in_docker(args.docker_image)
        sys.exit()

    if not PIPENV_PATH:
        logger.error("'pipenv' not found")
        sys.exit(1)

    global S3_BUCKET_NAME
    global S3_ARTIFACT_DIR

    S3_BUCKET_NAME, S3_ARTIFACT_DIR = get_s3_bucket_and_dir(args.s3_bucket)

    try:
        with open(args.template) as fobj:
            template_file = YAML().load(fobj)
    except Exception as error:
        logger.error('Failed to load template file! Encountered: '
                     f'{type(error).__name__}\n')
        sys.exit(1)

    api_resources = dict()
    lambda_functions = dict()

    for resource in template_file['Resources']:
        if template_file['Resources'][resource]['Type'] == \
                'AWS::Serverless::Function':
            runtime = \
                    template_file['Resources'][resource]['Properties'].get(
                        'Runtime',
                        get_global(template_file, 'Function', 'Runtime')
                    )

            if not runtime.lower().startswith('python'):
                logger.warning('Possum only packages Python based Lambda '
                               f' functions! Found runtime "{runtime}" for  '
                               f'function "{resource}" This Lambda function '
                               'will be skipped. You will need to package this '
                               'function separately before deploying.')
                continue

            else:
                lambda_functions[resource] = \
                    template_file['Resources'][resource]

        elif template_file['Resources'][resource]['Type'] == \
                'AWS::Serverless::Api':
            # Server::Api resource. If it has a 'DefinitionUri' parameter
            # that DOES NOT start with s3://, this swagger file must be
            # shipped and the template updated.
            if 'DefinitionUri' in \
                    template_file['Resources'][resource]['Properties'] \
                    and \
                    not template_file['Resources'][resource]['Properties']['DefinitionUri'].startswith('s3://'):
                api_resources[resource] = template_file['Resources'][resource]

    logger.info("\nThe following functions will be packaged and deployed:")
    for func in lambda_functions.keys():
        logger.info(f"  - {func}")

    logger.info("\nThe following swagger files will be deployed:")
    for api in api_resources.keys():
        logger.info(f"  - {api}")

    try:
        possum_file = PossumFile()
    except scanner.ScannerError:
        logger.error(f"The Possum file '{POSSUM_PATH}' is invalid!")
        sys.exit(1)

    build_directory = tempfile.mkdtemp(suffix='-build', prefix='possum-')
    logger.info(f'\nBuild directory: {build_directory}\n')

    build_artifact_directory = os.path.join(build_directory, 's3_artifacts')
    os.mkdir(build_artifact_directory)

    for logical_id, api_resource in api_resources.items():
        swagger_src = os.path.join(
            WORKING_DIR, api_resource['Properties']['DefinitionUri'])

        swagger_dst = os.path.join(
            build_artifact_directory,
            f'{logical_id}.swagger'
        )

        shutil.copyfile(swagger_src, swagger_dst)

        update_template_resource(
            template_file,
            logical_id,
            s3_object=os.path.basename(swagger_dst),
            resource_param='DefinitionUri')

    for func, values in lambda_functions.items():
        func_source_dir = os.path.join(
            WORKING_DIR, values['Properties']['CodeUri'])

        func_build_dir = os.path.join(build_directory, func)

        if possum_file.check_hash(func, func_source_dir) and not args.clean:
            last_s3_uri = possum_file.get_last_s3_uri(func)
            if last_s3_uri:
                logger.info(f'{func}: No changes detected')
                logger.info(f'{func}: Using S3 artifact: {last_s3_uri}\n')
                update_template_resource(
                    template_file,
                    func,
                    s3_uri=last_s3_uri)
                continue

        shutil.copytree(func_source_dir, func_build_dir)
        os.chdir(func_build_dir)
        logger.info(f'{func}: Working dir: {func_build_dir}')

        requirements_files = ('Pipfile', 'Pipfile.lock', 'requirements.txt')
        if [i for i in os.listdir('.') if i in requirements_files]:
            logger.info(f'{func}: Creating virtual environment...')
            create_virtual_environment()

            venv_path = get_virtual_environment_path()

            logger.info(f'{func}: Virtual environment created at {venv_path}')

            do_not_copy = get_existing_site_packages(venv_path)

            logger.info(f'{func}: Installing requirements...')
            install_packages()

            logger.info(f'{func}: Copying installed packages...')
            copy_installed_packages(venv_path, do_not_copy)

            logger.info(f'{func}: Removing Lambda build virtual environment...')
            remove_virtualenv()

        logger.info(f'{func}: Creating Lambda function Zip archive...')

        artifact = create_deployment_package(
            func_build_dir, build_artifact_directory)

        update_template_resource(
            template_file,
            func,
            s3_object=artifact
        )
        possum_file.set_s3_uri(
            func, template_file['Resources'][func]['Properties']['CodeUri'])
        logger.info('')

    upload_artifacts(
        build_artifact_directory,
        args.profile
    )

    logger.info('\nRemoving build directory...')
    shutil.rmtree(build_directory)

    stream = io.StringIO()
    YAML().dump(template_file, stream)
    deployment_template = stream.getvalue()

    if not args.output_template:
        logger.info('\nUpdated SAM deployment template:\n')
        print(deployment_template)
    else:
        logger.info("Writing deployment template to "
                    f"'{args.output_template}'...\n")
        with open(os.path.join(WORKING_DIR, args.output_template),
                  'wt') as fobj:
            fobj.write(deployment_template)

    possum_file.save()
