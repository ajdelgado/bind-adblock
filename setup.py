#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup script"""

import configparser
import setuptools

config = configparser.ConfigParser()
config.read('setup.cfg')

setuptools.setup(
    version=config['metadata']['version'],
    name=config['metadata']['name'],
    long_description="README.md",
    long_description_content_type="text/markdown",
)
