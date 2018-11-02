import re
from setuptools import find_packages, setup


def about_module():
    values = dict()
    with open('possum/__init__.py', 'r') as f:
        dunders = list()
        for l in f.readlines():
            if dunder_regex.match(l):
                dunders.append(l)
        exec('\n'.join(dunders), values)
    return values


def get_readme():
    with open('README.rst', 'r') as f:
        readme = f.read()
    return readme


dunder_regex = re.compile(r'^__\w+__\s*=.*$')

about = about_module()

requirements = [
    "boto3>=1.9.36",
    "docker>=3.5.1",
    "ruamel.yaml>=0.15.76"
]

setup(
    name=about['__title__'],
    version=about['__version__'],
    description='A packaging tool for Python AWS serverless applications.',
    long_description=get_readme(),
    author=about['__author__'],
    author_email=about['__author_email__'],
    url='https://github.com/brysontyrrell/Possum',
    license=about['__license__'],
    scripts=[
        'bin/possum'
    ],
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=requirements,
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
