#!/usr/bin/env python
# -*- coding: utf-8 -*-

from sys import exit
try:
    print 'Checking for PyQt4...'
    import PyQt4
except:
    print 'PL2Edit requires PyQt4 to work! :('
    print 'Since setuptools is not able to install PyQt4, you have to install it manually...\n'
    print 'Sorry for the inconvenience.'
    exit()

from os import path
from setuptools import setup, Extension

_path = path.abspath(path.dirname(__file__))
with open(path.join(_path, 'README.rst')) as f:
    long_desc = f.read()

info = {}
with open(path.join(_path, 'pl2editor/info.py')) as f:
    exec(f.read(), info)

setup(
    name = 'PL2Edit',
    version = info['__version__'],
    author = 'Maurizio Berti',
    author_email = 'maurizio.berti@gmail.com',
    url = info['__codeurl__'],
    description = 'Editor for Ploytec PL2 synthesizer',
    license = 'GPL',
    install_requires = ['pyalsa'], 
    packages = [
        'pl2editor',
    ],
    include_package_data=True,
    scripts = [
        'pl2edit.py',
        'pl2edit', 
    ],
)
