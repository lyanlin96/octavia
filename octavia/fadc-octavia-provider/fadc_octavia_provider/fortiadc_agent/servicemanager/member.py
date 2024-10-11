# Copyright (c) 2024  Fortinet Inc.
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

"""

"""

from fadc_octavia_provider.fortiadc_agent.fadc_api.slb.real_server import RS
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

class Member(object):

    def __init__(self, fadc_driver):
        self.rs = RS(fadc_driver.host, fadc_driver.connector, fadc_driver.conf.debug_mode)

    def create(self, member):
        LOG.debug("create member")
        self.rs.create(member)

    def delete(self, member):
        LOG.debug("delete member")
        self.rs.delete(member)
    def update(self, member):
        LOG.debug("update member")

        self.rs.update(member)

    def get_member_availability(self, member):
        return self.rs.get_availability(member)


