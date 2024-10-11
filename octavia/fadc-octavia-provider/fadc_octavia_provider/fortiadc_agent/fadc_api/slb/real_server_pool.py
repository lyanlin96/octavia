
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

from fadc_octavia_provider.fortiadc_agent.fadc_api.base import FADC
from oslo_log import log as logging
#from fortinet_openstack_agent import exceptions as f_exceptions
import sys
LOG = logging.getLogger(__name__)


class RSpool(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/load_balance_pool"
        self.host = host
        self.connector = connector
        self.verbose = verbose
        super(RSpool, self).__init__(host, connector, verbose)

    def create(self, pool):
        errcodes = {-15}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, pool)
        if not ok:
            raise Exception('Create pool %s failed' %(pool.id))
    def delete(self, pool):
        errcodes = {-1}
        #errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, pool)
        if not ok:
            raise Exception('Delete pool %s failed' %(pool.id))
            #raise f_exceptions.NotFoundException('Delete pool %s failed' %(pool.id))
    def getone(self, pool):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, pool)

    #def update(self, pool, hc_id, opt):
    def update(self, pool):
        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, pool)
        if not ok:
            #raise Exception('Cannot update pool %s with healthmonitor %s' %(pool.id, hc_id))
            raise Exception('Cannot update pool %s' %(pool.id))
    def mapping(self, pool):
        return {
            'mkey':pool.id,
            'health_check': pool.health_check if hasattr(pool,'health_check') else "disable",
            'health_check_list': pool.health_check_list if hasattr(pool,'health_check_list') else "",
        }
    def attrs_set_on_device(self):
        return {
            'pool_type':"ipv4",
            'health_check_realtionshiop':"AND",
            'rs_profile':"NONE",
        }
