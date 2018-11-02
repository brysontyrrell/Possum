import os
import sys
import tempfile
import time

import docker
from docker.errors import APIError, ImageNotFound

from possum.config import logger


def run_in_docker(user_dir, possum_path, image_name):
    command = sys.argv

    command[0] = 'possum'
    command.pop(command.index('--docker'))

    try:
        command.pop(command.index('--docker-image') + 1)
        command.pop(command.index('--docker-image'))
    except ValueError:
        pass

    docker_directory = tempfile.mkdtemp(
        suffix='-docker', prefix='possum-', dir='/tmp')
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
                os.path.join(user_dir, '.aws'): {
                    'bind': '/root/.aws',
                    'mode': 'ro'
                },
                os.path.dirname(possum_path): {
                    'bind': '/root/.possum',
                    'mode': 'rw'
                },
                os.getcwd(): {
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
