# Copyright (c) 2017  Fortinet Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import fortinet_neutron_lbaas
from setuptools import setup

setup(name='fortinet_neutron_lbaas',
            version=fortinet_neutron_lbaas.__version__,
            description='Fortinet Plugin Driver',
            url='',
            author='Fortinet',
            author_email='',
            license='Apache-2.0',
            packages=setuptools.find_packages(exclude=['test*']),
            zip_safe=False)
