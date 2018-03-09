import argparse
import errno
import io
import os
import shutil
import subprocess
import tempfile
import time
import uuid

import boto3
from ruamel.yaml import YAML


def arguments():
    parser = argparse.ArgumentParser(
        'possum',
        description='Possum is a utility to package and deploy Python-based '
                    'serverless applications using the Amazon Serverless '
                    'Application model with per-function dependencies using '
                    'Pipfiles.'
    )

    parser.add_argument(
        's3_bucket',
        help='The S3 bucket to upload artifacts',
        type=str,
        metavar='s3_bucket'
    )

    parser.add_argument(
        '-t', '--template',
        help='The filename of the SAM template',
        type=str,
        default='template.yaml',
        metavar='template'
    )

    parser.add_argument(
        '-o', '--output-template',
        help='Optional filename for the output template',
        type=str,
        metavar='output'
    )

    return parser.parse_args()


args = arguments()
print(args)

PIPENV = shutil.which('pipenv')
if not PIPENV:
    raise Exception('pipenv is not installed')

S3 = boto3.resource('s3')
S3_BUCKET_NAME = args.s3_bucket
S3_ARTIFACT_DIR = f'possum-{int(time.time())}'

WORKING_DIR = os.getcwd()

try:
    with open(args.template) as fobj:
        yaml = YAML()
        TEMPLATE = yaml.load(fobj)
except Exception as error:
    print('ERROR: Failed to load template file! Encountered: '
          f'{type(error).__name__}\n')
    raise SystemExit

LAMBDA_FUNCTIONS = dict()

for resource in TEMPLATE['Resources']:
    if TEMPLATE['Resources'][resource]['Type'] == 'AWS::Serverless::Function':
        runtime = TEMPLATE['Resources'][resource]['Properties']['Runtime']
        if not runtime.lower().startswith('python'):
            print('ERROR: Possum only deploys Python based Lambda functions! '
                  f'Found runtime "{runtime}" for function "{resource}"\n')
            raise SystemExit
        else:
            LAMBDA_FUNCTIONS[resource] = TEMPLATE['Resources'][resource]

# PROJECT_DIRS = [
#     d for d in os.listdir(WORKING_DIR)
#     if not d.startswith('.') and os.path.isdir(d)
# ]
#
# for func in LAMBDA_FUNCTIONS:
#     if func not in PROJECT_DIRS:
#         print(f'WARNING: No matching directory found for Lambda function '
#               f'"{func}" in template!')
#         raise SystemExit

print("\nThe following functions will be packaged and deployed:")
for func in LAMBDA_FUNCTIONS.keys():
    print(f"  - {func}")

BUILD_DIR = tempfile.mkdtemp(suffix='-build', prefix='possum-')
print(f'\nBuild directory: {BUILD_DIR}\n')

ARTIFACTS_DIR = os.path.join(BUILD_DIR, 's3_artifacts')
os.mkdir(ARTIFACTS_DIR)


def create_virtual_environment():
    p = subprocess.Popen(
        [
            PIPENV,
            '--three'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    p.communicate()


def get_virtual_environment_path():
    p = subprocess.Popen(
        [
            PIPENV,
            '--venv'
        ],
        stdout=subprocess.PIPE
    )
    result = p.communicate()
    return result[0].decode('ascii').strip('\n')


def get_existing_site_packages(venv_path):
    path = os.path.join(venv_path, 'lib/python3.6/site-packages')
    return os.listdir(path)


def install_packages():
    p = subprocess.Popen(
        [
            PIPENV,
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


def create_deployment_package(build_dir):
    archive_name = uuid.uuid4().hex
    shutil.make_archive(
        archive_name,
        'zip',
        root_dir=build_dir,
        base_dir='./'
    )

    print('Moving Zip archive to the artifacts directory...')
    shutil.move(archive_name + '.zip', ARTIFACTS_DIR)
    return archive_name + '.zip'


def remove_virtualenv():
    p = subprocess.Popen(
        [
            PIPENV,
            '--rm'
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    p.communicate()


def update_template_function(resource, s3_object):
    TEMPLATE['Resources'][resource]['Properties']['CodeUri'] = \
        f's3://{S3_BUCKET_NAME}/{S3_ARTIFACT_DIR}/{s3_object}'


for func, values in LAMBDA_FUNCTIONS.items():
    func_dir = os.path.join(BUILD_DIR, func)

    shutil.copytree(os.path.join(WORKING_DIR, values['Properties']['CodeUri']), func_dir)
    os.chdir(func_dir)
    print(f'{func}: Working dir: {func_dir}')

    if [i for i in os.listdir('.') if i in ('Pipfile', 'Pipfile.lock')]:
        print(f'{func}: Creating virtual environment...')
        create_virtual_environment()

        venv_path = get_virtual_environment_path()

        print(f'{func}: Virtual environment created at {venv_path}')

        do_not_copy = get_existing_site_packages(venv_path)

        print(f'{func}: Installing requirements...')
        install_packages()

        print(f'{func}: Copying installed packages...')
        copy_installed_packages(venv_path, do_not_copy)

        print(f'{func}: Removing Lambda build virtual environment...')
        remove_virtualenv()

    print(f'{func}: Creating Lambda function Zip archive...')
    artifact = create_deployment_package(func_dir)
    update_template_function(func, artifact)
    print('')


def upload_artifacts():
    print(f'\nUploading all Lambda build artifacts to: {S3_ARTIFACT_DIR}')
    os.chdir(ARTIFACTS_DIR)
    for artifact in os.listdir('.'):
        print(f'Uploading artifact: {artifact}')
        S3.Bucket(S3_BUCKET_NAME).upload_file(
            artifact, os.path.join(S3_ARTIFACT_DIR, artifact))


upload_artifacts()

print('\nRemoving build directory...')
shutil.rmtree(BUILD_DIR)

stream = io.StringIO()
yaml.dump(TEMPLATE, stream)
deployment_template = stream.getvalue()

if not args.output_template:
    print('\nUpdated SAM deployment template:\n')
    print(deployment_template)
else:
    print(f"Writing deployment template to '{args.output_template}'...\n")
    with open(os.path.join(WORKING_DIR, args.output_template), 'wt') as fobj:
        fobj.write(deployment_template)
