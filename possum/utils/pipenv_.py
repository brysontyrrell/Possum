import shutil
import subprocess

from possum.exc import PipenvPathNotFound


class PipenvWrapper:
    def __init__(self):
        self.path = shutil.which('pipenv')

        if not self.path:
            raise PipenvPathNotFound

    def create_virtual_environment(self):
        p = subprocess.Popen(
            [self.path, '--three'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        p.communicate()

    def get_virtual_environment_path(self):
        p = subprocess.Popen(
            [self.path, '--venv'],
            stdout=subprocess.PIPE
        )
        result = p.communicate()
        return result[0].decode('ascii').strip('\n')

    def install_packages(self):
        p = subprocess.Popen(
            [self.path, 'install'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        p.communicate()

    def remove_virtualenv(self):
        p = subprocess.Popen(
            [self.path, '--rm'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        p.communicate()
