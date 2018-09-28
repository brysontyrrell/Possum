import re
from setuptools import find_packages, setup

regex = re.compile(r'^__\w+__\s*=.*$')

about = dict()
with open('possum/__init__.py', 'r') as f:
    dunders = list()
    for l in f.readlines():
        if regex.match(l):
            dunders.append(l)
    exec('\n'.join(dunders), about)

with open('README.rst', 'r') as f:
    readme = f.read()

setup(
    name=about['__title__'],
    version=about['__version__'],
    description='A packaging tool for Python AWS serverless applications.',
    long_description=readme,
    author=about['__author__'],
    author_email=about['__author_email__'],
    url='https://github.com/brysontyrrell/Possum',
    license=about['__license__'],
    scripts=[
        'bin/possum'
    ],
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'boto3>=1.6.6',
        'docker>=3.2.1',
        'ruamel.yaml>=0.15.35'
    ],
    extras_require={},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Build Tools'
    ],
    zip_safe=False
)
