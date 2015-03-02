#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
import os
from setuptools import setup


HERE = os.path.abspath(os.path.dirname(__file__))


def make_readme(root_path):
    FILES = ('README.rst', 'LICENSE', 'CHANGELOG', 'CONTRIBUTORS')
    for filename in FILES:
        filepath = os.path.realpath(os.path.join(HERE, filename))
        if os.path.isfile(filepath):
            with open(filepath, mode='r') as f:
                yield f.read()


LONG_DESCRIPTION = "\r\n\r\n----\r\n\r\n".join(make_readme(HERE))


setup(
    name='blanket',
    version='0.1.0',
    py_modules=(
        'blanket',
    ),
    packages=(),
    install_requires=(
        'WebOb>=1.4',
    ),
    author='Keryn Knight',
    author_email='python-package@kerynknight.com',
    description="playing with WSGI",
    long_description=LONG_DESCRIPTION,
    include_package_data=True,
    zip_safe=False,
    license="BSD License",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Environment :: Web Environment',
        'Topic :: Internet :: WWW/HTTP',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
)
