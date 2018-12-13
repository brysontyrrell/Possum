import hashlib
import os
import time


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
