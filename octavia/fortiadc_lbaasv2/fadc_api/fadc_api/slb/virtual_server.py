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

"""

"""

from fadc_api.base import FADC
import sys
from oslo_log import log as logging
from fortinet_openstack_agent import exceptions as f_exceptions
LOG = logging.getLogger(__name__)

vdom_route = "?vdom="
pkey_route = "&pkey="
class VirtualServer(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/load_balance_virtual_server"
        super(VirtualServer, self).__init__(host, connector, verbose)

    def create(self, vs):
        errcodes = {-15}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vs)
        if not ok:
            raise Exception('Create vs %s failed' %(vs.id))
    def delete(self, vs):
        #errcodes = {-1}
        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vs)
        if not ok:
            raise f_exceptions.NotFoundException('Delete vs %s failed' %(vs.id))
            #raise Exception('Delete vs %s failed' %(vs.id))
    def getall(self, vs):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, vs)
    def getone(self, vs):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, vs)
    def update(self, vs):
        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vs)
        if not ok:
            raise Exception('Update vs %s failed' %(vs.id))
    def mapping(self, vs):
        return {
            'status':vs.fadc_status,
            'type':vs.vs_type,
            'address':vs.loadbalancer.vip_address,
            'packet-fwd-method':vs.fadc_pktfwd,
            'port':str(vs.protocol_port),
            'connection-limit':str(vs.fadc_connection_limit),
            'mkey':vs.id,
            'interface':vs.fadc_dev_intf,
            'profile':vs.fadc_profile,
            'persistence':vs.fadc_persistence,
            'method':vs.fadc_method,
            'pool':vs.fadc_pool_id,
            'source-pool-list':"openstack_lbaas" if hasattr(vs, "fadc_nat_pool_name") else "",
            'client_ssl_profile':vs.fadc_client_ssl_prof,
        }
    def attrs_set_on_device(self):
        return {
            'addr-type':"ipv4",
            'address6':"",
            'protocol':"",
            'content-routing':"disable",
            'content-rewriting':"",
            'error-msg':"",
            'warmup':"0",
            'warmrate':"100",
            'connection-rate-limit':"0",
            'traffic-log':"disable",
            'alone':"enable",
            'trans-rate-limit':"",
            'scripting_flag':"",
            'ssl-mirror':"disable",
            'content-routing-list':"",
            'content-rewriting-list':"",
            'scripting_list':"",
            'comments':"",
            'traffic-group':"default",
            'ssl-mirror-intf':"",
            'error-page':"",
            'waf-profile':"",
            'auth_policy':"",
            'l2-exception-list':"",
            'pagespeed':""
        }
    def get_all_vs_stats(self, all_vs, ptype):

        vs_stats = {'bytesIn':0,
                    'bytesOut':0,
                    'curConns':0,
                    'totConns':0
                   }
        if all_vs:
            _all=self.getall(all_vs[0])
            vs_on_device = [ele['mkey'] for ele in _all]

        for vs in all_vs:
            if vs.id not in vs_on_device:
                raise Exception('Cannot get vs stat')

            #ptype = "0"
            count = "60"
            param = "&range=" + ptype + "&mkey=" + vs.id
            #url = "/status_history/openstack_vs" + vdom_route + vs.tenant_id + param
            url = "/status_history/vs" + vdom_route + vs.tenant_id + param

            response = self.get(url)
            ok = self.response_handler(response, {})

            if ok:
                vs_stats['bytesIn'] = sum(int(e) for e in response.json()['payload']['in_bytes'])
                vs_stats['bytesOut'] = sum (int(e) for e in response.json()['payload']['out_bytes'])
                vs_stats['curConns'] = sum (int(e) for e in response.json()['payload']['current_sessions'])
                vs_stats['totConns'] = sum (int(e) for e in (response.json()['payload']['total_sessions']))

        return vs_stats


