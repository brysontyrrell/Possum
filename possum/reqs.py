import json
import os
import re

import toml

CWD = os.getcwd()

dunder_regex = re.compile(r'^__\w+__\s*=.*$')
import_regex = re.compile(r'^(?:import|from)\s(.+?)(?:\..*$|$|\s.+$)')


def get_pipfile_packages():
    pipfile = toml.load(os.path.join(CWD, 'Pipfile'))

    with open(os.path.join(CWD, 'Pipfile.lock'), 'r') as f:
        pipfile_lock = json.load(f)

    values = dict()

    for r in pipfile_lock['default'].keys():
        if r in pipfile['packages'].keys():
            # Git installed packages will not have version values
            version = pipfile_lock['default'][r].get('version')

            if not version:
                git_url = pipfile_lock['default'][r].get('git')
                if git_url:
                    values[r] = {'pip': f'git+{git_url}#egg={r}'}
            else:
                values[r] = {'pip': f'{r}{version}'}

    return values


def get_imports(path):
    values = list()

    with open(path, 'r') as f:
        for l in f.readlines():
            match = import_regex.match(l)
            if match:
                pkg_name = match.group(1)
                if pkg_name not in ('boto3', 'botocore'):
                    values.append(pkg_name)

    return set(values)


def generate_requirements(pipfile_packages, lambda_packages, dest):
    packages = [
        pipfile_packages[i]['pip']
        for i in lambda_packages
        if i in pipfile_packages.keys()
    ]

    if packages:
        with open(os.path.join(dest, 'requirements.txt'), 'w') as f:
            for package in packages:
                f.write(package + '\n')

        return packages
    else:
        return None
