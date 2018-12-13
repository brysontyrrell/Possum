import hashlib
import os
import sys

from ruamel.yaml import YAML

from possum.config import logger
from possum.utils.general import hash_directory


def _possum_name():
    cwd = os.getcwd()
    return f'{os.path.split(cwd)[-1]}-' \
           f'{hashlib.sha1(cwd.encode()).hexdigest()[-8:]}'


def get_possum_path(user_dir):
    possum_dir = os.path.join(user_dir, '.possum')
    if not os.path.exists(possum_dir):
        logger.info('Creating Possum directory...')
        os.mkdir(possum_dir)
    elif not os.path.isdir(possum_dir):
        logger.error(f"'{possum_dir}' is not a directory! Delete to "
                     "allow Possum to recreate the directory")
        sys.exit(1)

    return os.path.join(possum_dir, _possum_name())


class PossumFile(object):
    def __init__(self, user_dir):
        self.path = get_possum_path(user_dir)
        try:
            with open(self.path, 'r') as f_obj:
                data = YAML().load(f_obj)
        except FileNotFoundError:
            data = {
                'lastRun': dict(),
                's3Uris': dict()
            }

        self._data = data

    def save(self):
        with open(self.path, 'w') as f_obj:
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
