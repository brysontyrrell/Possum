import argparse
import io
import os
import shutil
import sys
import tempfile

from ruamel.yaml import scanner, YAML

from possum import __version__
from possum.config import logger, configure_logger
from possum.exc import PipenvPathNotFound
from possum.packages import (
    copy_installed_packages,
    create_lambda_package,
    get_existing_site_packages,
    upload_packages
)
from possum.reqs import get_pipfile_packages, get_imports, generate_requirements
from possum.template import get_global, update_template_resource, SAMTemplate
from possum.utils import (
    build_docker_image,
    get_s3_bucket_and_dir,
    run_in_docker,
    PipenvWrapper,
    PossumFile,
)

WORKING_DIR = os.getcwd()
USER_DIR = os.path.expanduser('~')
S3_BUCKET_NAME = ''
S3_ARTIFACT_DIR = ''


class CommandHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        parts = super(argparse.RawDescriptionHelpFormatter, self)._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


def arguments():
    """Parse command line arguments when invoked as a CLI tool.

    :returns: Parsed arguments
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        'possum',
        description='Possum is a utility to package Python-based serverless '
                    'applications using the Amazon Serverless Application '
                    'model with per-function dependencies.',
        formatter_class=CommandHelpFormatter
    )

    parser.add_argument(
        '-v', '--version',
        help='Display version information.',
        action='version',
        version=f'Possum {__version__}'
    )
    parser._optionals.title = 'Global Options'

    subparsers = parser.add_subparsers(title='Commands')

    main_legacy_parser = subparsers.add_parser(
        'package',
        help='Package the Serverless application, upload to S3, and generate a '
             'deployment template file.'
    )
    main_legacy_parser.set_defaults(func=main_legacy)

    main_legacy_parser.add_argument(
        's3_bucket',
        help="The S3 bucket to upload artifacts. You may optionally pass a "
             "path within the bucket to store the Lambda artifacts (defaults "
             "to 'possum-{timestamp}').",
        metavar='s3_bucket'
    )

    main_legacy_parser.add_argument(
        '-t', '--template',
        help='The filename of the SAM template.',
        default='template.yaml',
        metavar='template'
    )

    main_legacy_parser.add_argument(
        '-o', '--output-template',
        help='Optional filename for the output template.',
        metavar='output'
    )

    main_legacy_parser.add_argument(
        '-p', '--profile',
        help='Optional profile name for AWS credentials.',
        metavar='profile_name'
    )

    main_legacy_parser.add_argument(
        '-c', '--clean',
        help='Build all Lambda packages, ignoring previous run.',
        action='store_true'
    )

    main_legacy_parser.add_argument(
        '--docker',
        help='Build Lambda packages within a Docker container environment.',
        action='store_true'
    )

    main_legacy_parser.add_argument(
        '--docker-image',
        help="Specify a Docker image to use (defaults to 'possum:latest').",
        default='possum:latest',
        metavar='image_name'
    )

    gen_reqs_parser = subparsers.add_parser(
        'generate-requirements',
        help="Generate 'requirements.txt' files for each Lambda function from "
             "the project's Pipfile (BETA)."
    )
    gen_reqs_parser.set_defaults(func=gen_reqs)

    gen_reqs_parser.add_argument(
        '-t', '--template',
        help='The filename of the SAM template.',
        default='template.yaml',
        metavar='template'
    )

    docker_image_parser = subparsers.add_parser(
        'build-docker-image',
        help="Build the default 'possum' Docker image to run build jobs within."
    )
    docker_image_parser.set_defaults(func=docker_image)

    return parser.parse_args()


def gen_reqs(args):
    if not os.path.exists(os.path.join(WORKING_DIR, 'Pipfile')) and \
            os.path.exists(os.path.join(WORKING_DIR, 'Pipfile.lock')):
        logger.error(
            "This feature requires a root level 'Pipfile' and 'Pipfile.lock'")
        sys.exit(1)

    template = SAMTemplate(args.template)

    pipfile_packages = get_pipfile_packages()

    logger.info('Evaluating Lambda function dependencies...\n')
    for k, v in template.lambda_resources.items():
        handler_file = template.get_lambda_handler(k)
        if not handler_file:
            logger.error(f"{k}: There was no 'Handler' found for the Lambda "
                         f"function and it is being skipped!\n")
            continue

        lambda_code_dir = v['Properties']['CodeUri']

        imports = get_imports(
            os.path.join(WORKING_DIR, lambda_code_dir, handler_file))

        requirements = generate_requirements(
            pipfile_packages, imports, lambda_code_dir)

        if requirements:
            logger.info(f"{k}: A requirements.txt file has been generated with "
                        "the following packages:")
            logger.info(f"{k}: {', '.join(requirements)}\n")
        else:
            logger.info(f"{k}: No requirements.txt file generated\n")


def docker_image(args):
    build_docker_image()


def main_legacy(args):
    try:
        possum_file = PossumFile(USER_DIR)
    except scanner.ScannerError:
        logger.error(f"The Possum file could not be loaded!")
        sys.exit(1)

    if args.docker:
        if not args.docker_image:
            logger.error('A Docker image must be specified')
            sys.exit(1)

        run_in_docker(USER_DIR, possum_file.path, args.docker_image)
        sys.exit()

    try:
        pipenvw = PipenvWrapper()
    except PipenvPathNotFound:
        logger.error("'pipenv' could not be found!")
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
                    not (
                        template_file['Resources'][resource]['Properties']
                        ['DefinitionUri'].startswith('s3://')
                    ):
                api_resources[resource] = template_file['Resources'][resource]

    logger.info("\nThe following functions will be packaged and deployed:")
    for func in lambda_functions.keys():
        logger.info(f"  - {func}")

    logger.info("\nThe following swagger files will be deployed:")
    for api in api_resources.keys():
        logger.info(f"  - {api}")

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
            S3_BUCKET_NAME,
            S3_ARTIFACT_DIR,
            s3_object=os.path.basename(swagger_dst),
            resource_param='DefinitionUri'
        )

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
                    S3_BUCKET_NAME,
                    S3_ARTIFACT_DIR,
                    s3_uri=last_s3_uri
                )
                continue

        shutil.copytree(func_source_dir, func_build_dir)
        os.chdir(func_build_dir)
        logger.info(f'{func}: Working dir: {func_build_dir}')

        requirements_files = ('Pipfile', 'Pipfile.lock', 'requirements.txt')
        if [i for i in os.listdir('.') if i in requirements_files]:
            logger.info(f'{func}: Creating virtual environment...')
            pipenvw.create_virtual_environment()

            pipenvw.get_virtual_environment_path()

            logger.info(f'{func}: Environment created at {pipenvw.venv_path}')

            do_not_copy = get_existing_site_packages(pipenvw.venv_path)

            logger.info(f'{func}: Installing requirements...')
            pipenvw.install_packages()

            logger.info(f'{func}: Copying installed packages...')
            copy_installed_packages(pipenvw.venv_path, do_not_copy)

            logger.info(f'{func}: Removing Lambda build environment...')
            pipenvw.remove_virtualenv()

        logger.info(f'{func}: Creating Lambda package...')

        artifact = create_lambda_package(
            func_build_dir, build_artifact_directory)

        update_template_resource(
            template_file,
            func,
            S3_BUCKET_NAME,
            S3_ARTIFACT_DIR,
            s3_object=artifact
        )
        possum_file.set_s3_uri(
            func, template_file['Resources'][func]['Properties']['CodeUri'])
        logger.info('')

    upload_packages(
        build_artifact_directory,
        S3_BUCKET_NAME,
        S3_ARTIFACT_DIR,
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


def main():
    configure_logger()

    args = arguments()
    args.func(args)

    sys.exit(0)
