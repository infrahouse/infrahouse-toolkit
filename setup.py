#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

CODEC = "utf-8"

with open("README.rst", encoding=CODEC) as readme_file:
    readme = readme_file.read()

HISTORY = "See git log"


def parse_requirements(req_file):
    """
    Parse file with requirements and return a dictionary
    consumable by setuptools.

    :param req_file: path to requirements file.
    :type req_file: str
    :return: Dictionary with requirements.
    :rtype: dict
    """
    with open(req_file, encoding=CODEC) as f_descr:
        reqs = f_descr.read().strip().split("\n")
    return [x for x in reqs if x and not x.strip().startswith("#")]


requirements = parse_requirements("requirements.txt")
test_requirements = parse_requirements("requirements_dev.txt")

setup(
    author="Oleksandr Kuzminskyi",
    author_email="aleks@infrahouse.com",
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    description="A collection of tools for building infrastructure.",
    entry_points={
        "console_scripts": [
            "ih-plan=infrahouse_toolkit.cli.ih_plan:ih_plan",
            "ih-s3-reprepro=infrahouse_toolkit.cli.ih_s3_reprepro:ih_s3_reprepro",
        ],
    },
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme + "\n\n" + HISTORY,
    include_package_data=True,
    keywords="infrahouse-toolkit",
    name="infrahouse-toolkit",
    packages=find_packages(include=["infrahouse_toolkit", "infrahouse_toolkit.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/infrahouse/infrahouse-toolkit",
    version="2.0.1",
    zip_safe=False,
)
