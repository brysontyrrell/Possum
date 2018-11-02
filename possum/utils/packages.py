import distutils.sysconfig as sysconfig
import errno
import os
import shutil
import sys
import uuid

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError, NoCredentialsError

from possum.config import logger


__all__ = [
    'get_existing_site_packages',
    'copy_installed_packages',
    'create_lambda_package',
    'upload_packages'
]


def _copy(src, dst):
    try:
        shutil.copytree(src, dst)
    except OSError as exc:
        if exc.errno == errno.ENOTDIR:
            shutil.copy(src, dst)
        else:
            raise


def get_existing_site_packages(venv_path):
    path = os.path.join(
        venv_path,
        'lib',
        'python' + sysconfig.get_python_version(),
        'site-packages'
    )
    return os.listdir(path)


def copy_installed_packages(venv_path, exclusions):
    path = os.path.join(venv_path, 'lib/python3.6/site-packages')
    packages = [i for i in os.listdir(path) if i not in exclusions]
    for package in packages:
        _copy(os.path.join(path, package), os.path.join(os.getcwd(), package))


def create_lambda_package(build_dir, artifact_directory):
    archive_name = uuid.uuid4().hex
    shutil.make_archive(
        archive_name,
        'zip',
        root_dir=build_dir,
        base_dir='./'
    )
    shutil.move(archive_name + '.zip', artifact_directory)
    return archive_name + '.zip'


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
