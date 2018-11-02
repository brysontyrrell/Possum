"""Print a list() of required modules for this project as determined by the
Pipfile and Pipfile.lock.
"""
import json
import os

import toml

PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))

pipfile = toml.load(os.path.join(PROJECT_DIR, 'Pipfile'))
with open(os.path.join(PROJECT_DIR, 'Pipfile.lock'), 'r') as f:
    pipfile_lock = json.load(f)

requirements = list()
for r in pipfile_lock['default'].keys():
    if r in pipfile['packages'].keys():
        requirements.append('{}{}'.format(
            r, pipfile_lock['default'][r]['version'].replace('==', '>=')))

print(json.dumps(requirements, indent=4))
