import re
from setuptools import setup

regex = re.compile(r'^__\w+__\s*=.*$')

about = dict()
with open('possum', 'r') as f:
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
    scripts=['possum'],
    python_requires='>=3.6',
    install_requires=[
        'boto3>=1.6.6',
        'ruamel.yaml>=0.15.35'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Build Tools'
    ]
)
