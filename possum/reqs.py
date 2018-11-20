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


def parse_requirements(lambda_path):
    requirements_filepath = os.path.join(lambda_path, 'requirements.txt')

    if os.path.isfile(requirements_filepath):
        with open(requirements_filepath, 'r') as rf:
            requirements_raw = rf.read().splitlines()
    else:
        return None

    requirements = {}
    for line in requirements_raw:
        try:
            name = line.split('==')[0]
        except IndexError:
            continue

        requirements[name] = {'pip': line}

    return requirements


def write_requirements(pipfile_packages, requirements_packages, dest):
    matched_requirements = \
        set([i.lower() for i in pipfile_packages.keys()]) & \
        set([i.lower() for i in requirements_packages.keys()])

    if matched_requirements:
        with open(os.path.join(dest, 'requirements.txt'), 'w') as f:
            for package in sorted(matched_requirements):
                f.write(pipfile_packages[package]['pip'] + '\n')

        return matched_requirements

    else:
        return None
