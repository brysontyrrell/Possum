import io
import os
import sys
import tempfile
import textwrap
import time

import docker
from docker.errors import APIError, BuildError, ImageNotFound

from possum.config import logger


def dockerfile(version):
    return io.BytesIO(
        textwrap.dedent(
            f'''\
            FROM lambci/lambda:build-python3.6
            
            RUN /var/lang/bin/pip install -U pip && \\
                /var/lang/bin/pip install pipenv
            
            RUN /var/lang/bin/pip install possum=={version}
            
            WORKDIR /var/task\
            '''
        ).encode()
    )


def build_docker_image(version):
    logger.info(f"Building 'possum:{version}' Docker image (this may take "
                "several minutes)...")
    client = docker.from_env()
    try:
        image = client.images.build(
            fileobj=dockerfile(version),
            tag=f'possum:{version}',
            quiet=False,
            rm=True,
            pull=True
        )

        logger.info("Tagging as 'latest'...")
        if image[0].tag('possum', 'latest'):
            image[0].reload()
        else:
            logger.info('Unable to add additional tag')

    except APIError as err:
        logger.error(f'Unable to build the Docker image: {err.explanation}')
        sys.exit(1)

    except BuildError as err:
        logger.error(f'Unable to build the Docker image: {err.msg}')
        sys.exit(1)

    image_id = image[0].short_id.split(':')[-1]
    logger.info("Image successfully created:\n"
                f"  ID: {image_id}\n"
                f"  Tags: {', '.join(image[0].tags)}")


def run_in_docker(user_dir, possum_path, image_name):
    command = sys.argv

    command[0] = 'possum'
    command.pop(command.index('--docker'))

    try:
        command.pop(command.index('--docker-image') + 1)
        command.pop(command.index('--docker-image'))
    except ValueError:
        pass

    # docker_directory = tempfile.mkdtemp(
    #     suffix='-docker', prefix='possum-', dir='/tmp')
    # logger.info(f'Working Docker directory: {docker_directory}')

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
                os.path.join(user_dir, '.aws'): {
                    'bind': '/root/.aws',
                    'mode': 'ro'
                },
                os.path.dirname(possum_path): {
                    'bind': '/root/.possum',
                    'mode': 'rw'
                },
                os.getcwd(): {
                    'bind': '/var/task',
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
