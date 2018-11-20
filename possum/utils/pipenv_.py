import os
import shutil
import subprocess

from possum.exc import PipenvPathNotFound


class PipenvWrapper:
    def __init__(self):
        self.pipenv_path = shutil.which('pipenv')

        if not self.pipenv_path:
            raise PipenvPathNotFound

        # Force pipenv to ignore any currently active pipenv environment
        os.environ['PIPENV_IGNORE_VIRTUALENVS'] = '1'

    @property
    def venv_path(self):
        return self.get_virtual_environment_path()

    def create_virtual_environment(self):
        p = subprocess.Popen(
            [self.pipenv_path, '--three'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        p.communicate()

    def get_virtual_environment_path(self):
        p = subprocess.Popen(
            [self.pipenv_path, '--venv'],
            stdout=subprocess.PIPE
        )
        result = p.communicate()
        return result[0].decode('ascii').strip('\n')

    def get_site_packages(self):
        return subprocess.check_output(
            [
                'pipenv', 'run', 'python', '-c',
                'from distutils.sysconfig import get_python_lib; '
                'print(get_python_lib())'
            ],
            universal_newlines=True
        ).strip()

    def install_packages(self):
        p = subprocess.Popen(
            [self.pipenv_path, 'install'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        p.communicate()

    def remove_virtualenv(self):
        p = subprocess.Popen(
            [self.pipenv_path, '--rm'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        p.communicate()

    def check_package_title(self, package):
        try:
            # Yes, this needs to be better, but performing this one-liner
            # though the Pipenv environment of the project only seems to work
            # when 'shell=True' is set.
            return subprocess.check_output(
                f'{self.pipenv_path} run python -c "import '
                f'{package}; print({package}.__title__)"',
                shell=True, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            return package
