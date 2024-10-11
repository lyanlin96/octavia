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
from fadc_octavia_provider.fortiadc_agent.fadc_api.base import HTTPStatus
from fadc_octavia_provider.fortiadc_agent.fadc_api.base import RequestAction
#from fortinet_openstack_agent import exceptions as f_exceptions
import sys
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

#sys_global_id = "-1"
sys_global_prefix = "/system_global"


class Vdom(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/vdom"
        super(Vdom, self).__init__(host, connector, verbose)
        res = self.get(sys_global_prefix)
        if res.status_code == HTTPStatus.OK:
            global_config = res.json()['payload']
            vdom_status = global_config['vdom-admin']
            if vdom_status == 'disable':
                global_config['vdom-admin'] = u'enable'
                #global_config.update({u'_id':u'-1'})
                res = self.put(sys_global_prefix, data=global_config)
                if res.status_code == HTTPStatus.OK:
                    LOG.debug("enable_vdom succeedED")
                else:
                    LOG.debug("enable_vdom failed")
        else:
            message = 'Vdom init failed'
            'status_code = '+str(res.status_code)
            raise Exception('%s' %(message))


    def create(self, vdom_name):
        errcodes = {-15}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name)
        if not ok:
            raise Exception('Create vdom failed')

    def delete(self, vdom_name):
        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name)
        if not ok:
            #raise f_exceptions.NotFoundException('Delete vdom failed')
            #modify 2024 
            raise Exception('Delete vdom failed')

    def getall(self):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes)

    def is_exist(self, vdom_name):
        for ele in self.getall():
            if ele['mkey'] == vdom_name:
                return True
        return False

    def action_handler(self, method, errcodes, vdom_name=None):
        if vdom_name:
            config = self.mapping(vdom_name)
        url = self.prefix
        if method == RequestAction.CREATE:
            response = self.post(url, None, config)
        elif method == RequestAction.DELETE:
            url += "?mkey=" + vdom_name
            response = self._delete(url)
        elif method == RequestAction.GETALL:
            response = self.get(url, None, None)

        ok = self.response_handler(response, errcodes)
        if ok and method == RequestAction.GETALL:
            return response.json()['payload']
        return ok

    def mapping(self, vdom_name):
        return {
            'concurrentsession':"",
            'ep':"",
            'hc':"",
            'l4cps':"",
            'l7cps':"",
            'l7rps':"",
            'lu':"",
            'mkey': vdom_name,
            'rs':"",
            'sp':"",
            'sslcps':"",
            'sslthroughput':"",
            'ug':"",
            'vs':""
        }



