
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
from fadc_octavia_provider.fortiadc_agent.fadc_api.base import RequestAction
from oslo_log import log as logging
#from fortinet_openstack_agent import exceptions as f_exceptions
import time
import sys
LOG = logging.getLogger(__name__)


vdom_route = "?vdom="
pkey_route = "&pkey="
class RS(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/load_balance_real_server"
        super(RS, self).__init__(host, connector, verbose)

    def create(self, rs):
        errcodes = {-15}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, rs)
        if not ok:
            raise Exception('Create real server failed')
        else:
            #do member child create
            time.sleep(1)
            child = RSpool_member(self.host, self.connector, self.verbose)
            if not child.is_exist(rs):
                child.create(rs)
    def delete(self, rs):
        # delete pool member first
        errcodes = {-1}
        #errcodes = {}
        child = RSpool_member(self.host, self.connector, self.verbose)
        child.delete(rs)
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, rs)
        if not ok:
            #raise f_exceptions.NotFoundException('Delete real server failed')
            raise Exception('Delete real server failed')

    def update(self, rs):
        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, rs)
        if not ok:
            raise Exception('Update server failed')
        else:
            #do member child update
            time.sleep(1)
            child = RSpool_member(self.host, self.connector, self.verbose)
            if child.is_exist(rs):
                child.update(rs)

    def getone(self, rs):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, rs)

    def mapping(self, member):
        return {
            'mkey': member.id,
            'address': member.ip_address,
            'status': "enable" if member.enabled else "disable",
        }
    def attrs_set_on_device(self):
        return {
            'address6': "::",
        }
    def get_availability(self, member):
        child = RSpool_member(self.host, self.connector, self.verbose)
        _all = child.getall(member)
        if not all:
            raise Exception("Get availability failed")
        for ele in _all:
            if ele['real_server_id'] == member.id:
                return ele['availability']
        return ""
class RSpool_member(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/load_balance_pool_child_pool_member"
        super(RSpool_member, self).__init__(host, connector, verbose)

    def create(self, member):
        errcodes = {-38}
        ok = self.action_handler(member, sys._getframe().f_code.co_name, errcodes)
        if not ok:
            raise Exception('Add member to pool failed')
    def delete(self, member):
        errcodes = {-1}
        ok = self.action_handler(member, sys._getframe().f_code.co_name, errcodes)
        if not ok:
            #raise f_exceptions.NotFoundException('delete member from pool failed')
            raise Exception('delete member from pool failed')
    def update(self, member):
        errcodes = {}
        ok = self.action_handler(member, sys._getframe().f_code.co_name, errcodes)
        if not ok:
            raise Exception('Update member from pool failed')

    def getall(self, member):
        errcodes = {}
        return self.action_handler(member, sys._getframe().f_code.co_name, errcodes)
    def is_exist(self, member):
        _all = self.getall(member)
        for ele in _all:
            if member.id == ele['real_server_id'] and str(member.protocol_port) == ele['port']:
                return True
        return False
    def mapping(self, member):
        return {
            'real_server_id': member.id,
            'port': str(member.protocol_port),
            'weight': str(member.weight),
        }
    def attrs_set_on_device(self):
        return {
            'status': "enable",
            'health_check_inherit': "enable",
            'm_health_check': "disable",
            'health_check_list': "",
            'm_health_check_realtionshio':"AND",
            'connlimit': "0",
            'recover':"0",
            'warmup':"0",
            'warmrate':"100",
            'connection-rate-limit':"0",
            'ssl':"disable",
            'rs_profile_inherit':"enable",
            'backup': "disable",
            'hc_status':"1",
            'mysql_group_id':"0",
            'mysql_read_only':"disable",
            'cookie':"",
            'address':"0.0.0.0",
            'address6':"::",
        }

    def action_handler(self, member, method, errcodes):
        config = self.mapping(member)
        vdom_name = member.project_id
        pkey = member.pool_id
        url = self.prefix + vdom_route + vdom_name + pkey_route + pkey
        ok = True
        if method in [RequestAction.DELETE, RequestAction.UPDATE]:
            found = 0
            all = self.getall(member)
            if not all:
                return not ok
            for ele in all:
                if ele['real_server_id'] == member.id:
                    url = self.prefix + vdom_route + vdom_name + pkey_route + pkey + "&mkey=" + ele['mkey']
                    if method == RequestAction.UPDATE:
                        ele.update(config)
                        config = ele
                    found = 1
                    break
            if not found:
                return not ok
        else:
            config.update(self.attrs_set_on_device())

        response = self.doAction(method)(url, None, config)

        ok = self.response_handler(response, errcodes)
        if ok and method == RequestAction.GETALL:
            return response.json()['payload']
        return ok


