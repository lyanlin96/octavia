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
from fadc_api.base import RequestAction
import sys
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

vdom_route = "?vdom="
class Interface(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/system_interface"
        super(Interface, self).__init__(host, connector, verbose)

    def attach_vdom(self, vdom_name, intf_names, ips):
        ok = 0
        res = self.getall()
        if res:
            for ele in res:
                if ele['mkey'] in intf_names:
                    #ele['vdom'] = unicode(vdom_name,"utf-8")
                    ele['vdom'] = vdom_name
                    if ele['mkey'] in ips:
                        ele['ip'] = ips[ele['mkey']]
                        ele['mode'] = 'static'
                    ok = self.update(ele)
                    if not ok:
                        raise Exception("Assign intf %s to vdom %s failed" %(ele['mkey'], vdom_name))

    def detach_vdom(self, vdom_name):
        ok = 0
        res = self.getall()
        if res:
            for ele in res:
                if ele['vdom'] == vdom_name:
                    ele['vdom'] = u'root'
                    ele['ip'] = u'0.0.0.0/0'
                    ok = self.update(ele)
                    if not ok:
                        raise Exception("Detach intf %s from vdom %s failed" %(ele['mkey'], vdom_name))

    def set_allowaccess(self, access):
        #for k, v in access.iteritems():
        #    LOG.error("%s %s" %(k, v))
        ok = 0
        res = self.getall()
        if res:
            for ele in res:
                if ele['mkey'] in access.keys():
                    ele['allowaccess'] = access[ele['mkey']]
                    ok = self.update(ele)
                    if not ok:
                        raise Exception("Update  intf %s with access %s failed" %(ele['mkey'], access[ele['mkey']]))

    def getall(self):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes)

    def update(self, intf):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, intf)

    def action_handler(self, method, errcodes, config=None):
        url = self.prefix
        if method == RequestAction.UPDATE:
            url += "?mkey=" + config['mkey']
            response = self.put(url, None, config)
        elif method == RequestAction.GETALL:
            response = self.get(url)

        ok = self.response_handler(response, errcodes)
        if ok and method == RequestAction.GETALL:
            return response.json()['payload']
        return ok

class Routing(FADC):
    def __init__(self, host, connector, verbose):
        self.prefix = "/router_static"
        super(Routing, self).__init__(host, connector, verbose)
    def create(self, gw, vdom_name):
        errcodes = {-1450, -15}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name, gw)
        if not ok:
            raise Exception("Create static route failed")
    def delete(self, gw, vdom_name):
        errcodes = {-1}
        _all = self.getall(vdom_name)
        if _all:
            for ele in _all:
                if ele['gw'] == gw:
                    ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name, ele['mkey'])
                    if not ok:
                        raise Exception("Delete static route failed")
                    break
    def getall(self,vdom_name):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name)

    def action_handler(self, method, errcodes, vdom_name, data=None):
        url = self.prefix
        if method == RequestAction.CREATE:
            url += vdom_route + vdom_name
            config = self.mapping(data)
            response = self.post(url, None, config)
        elif method == RequestAction.DELETE:
            url += vdom_route + vdom_name + "&mkey=" + data
            response = self._delete(url)
        elif method == RequestAction.GETALL:
            url += vdom_route + vdom_name
            response = self.get(url)

        ok = self.response_handler(response, errcodes)
        if ok and method == RequestAction.GETALL:
            return response.json()['payload']
        return ok
    def mapping(self, gw):
        return {
            'dest':"0.0.0.0/0",
            'gw':gw,
            'distance':"10"
        }
class Nat_pool(FADC):
    def __init__(self, host, connector, verbose):
        self.prefix = "/load_balance_ippool"
        super(Nat_pool, self).__init__(host, connector, verbose)
    def create(self, ip_range, intf, vdom_name):
        errcodes = {-15, -1212}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name, self.mapping(ip_range, intf))
        if not ok:
            raise Exception("Create NAT pool failed")
    def delete(self, intfs, vdom_name):
        errcodes = {-1}
        _all = self.getall(vdom_name)
        if _all:
            for ele in _all:
                if ele['interface'] in intfs:
                    ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name, ele['mkey'])
                    if not ok:
                        raise Exception("Delete nat pool failed")
    def getall(self,vdom_name):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, vdom_name)

    def mapping(self, ip_range, intf):
        return {
            "pool_type" : "ipv4",
            "mkey" : "openstack_lbaas",
            "ip-start"  : ip_range[0],
            "ip-end":  ip_range[1],
            "interface" :   intf
        }

    def action_handler(self, method, errcodes, vdom_name, data=None):
        url = self.prefix
        if method == RequestAction.DELETE:
            url += vdom_route + vdom_name + "&mkey=" + data
            response = self._delete(url)
        elif method == RequestAction.GETALL:
            url += vdom_route + vdom_name
            response = self.get(url)
        elif method == RequestAction.CREATE:
            url += vdom_route + vdom_name
            response = self.post(url, None, data)

        ok = self.response_handler(response, errcodes)
        if ok and method == RequestAction.GETALL:
            return response.json()['payload']
        return ok
