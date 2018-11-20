import distutils.sysconfig as sysconfig
import os
import shutil
import sys
import uuid
import zipfile

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError, NoCredentialsError

from possum.config import logger


__all__ = [
    'get_existing_site_packages',
    'move_installed_packages',
    'create_lambda_package',
    'upload_packages'
]


def get_existing_site_packages(venv_path):
    path = os.path.join(
        venv_path,
        'lib',
        'python' + sysconfig.get_python_version(),
        'site-packages'
    )
    return os.listdir(path)


# def move_installed_packages(venv_path, exclusions):
def move_installed_packages(site_packages_path, exclusions):
    # path = os.path.join(venv_path, 'lib/python3.6/site-packages')
    packages = [i for i in os.listdir(site_packages_path) if i not in exclusions]
    for package in packages:
        shutil.move(
            os.path.join(site_packages_path, package),
            os.path.join(os.getcwd(), package)
        )


def create_lambda_package(build_dir, artifact_directory):
    archive_name = uuid.uuid4().hex
    path_len = len(build_dir)

    with zipfile.ZipFile(os.path.join(artifact_directory, archive_name),
                         'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(build_dir):
            base_dir = root[path_len:]
            for file in files:
                zip_file.write(
                    os.path.join(root, file),
                    os.path.join(base_dir, file)
                )

    return archive_name


def upload_packages(package_directory, bucket_name,
                    bucket_dir, profile_name=None):
    session = boto3.Session(profile_name=profile_name)
    s3_client = session.resource('s3')

    os.chdir(package_directory)
    logger.info(f'Uploading all Lambda packages to: {bucket_dir}')

    for artifact in os.listdir('.'):
        logger.info(f'Uploading package: {artifact}')
        try:
            s3_client.Bucket(bucket_name).upload_file(
                artifact, os.path.join(bucket_dir, artifact))
        except NoCredentialsError:
            logger.error('Unable to upload packages to the S3 bucket. Boto3 '
                         'was unable to locate credentials!')
            sys.exit(1)
        except (S3UploadFailedError, ClientError)as err:
            logger.error('Failed to upload the package to the S3 bucket! '
                         f'Encountered:\n{err}')
            sys.exit(1)
