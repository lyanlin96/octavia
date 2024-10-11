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
from fadc_api.slb.real_server_pool import RSpool
from fortinet_openstack_agent import exceptions as f_exceptions
import sys
from oslo_log import log as logging
LOG = logging.getLogger(__name__)


allow_ssl_version = ["sslv3", "tlsv1.0", "tlsv1.1", "tlsv1.2"]
ssl_ciphers = [
"DHE-RSA-AES256-GCM-SHA384",
"DHE-RSA-AES256-SHA256",
"DHE-RSA-AES256-SHA",
"AES256-GCM-SHA384",
"AES256-SHA256",
"AES256-SHA",
"DHE-RSA-AES128-GCM-SHA256",
"DHE-RSA-AES128-SHA256",
"DHE-RSA-AES128-SHA",
"AES128-GCM-SHA256",
"AES128-SHA256",
"AES128-SHA",
"RC4-SHA",
"RC4-MD5",
"EDH-RSA-DES-CBC3-SHA",
"DES-CBC3-SHA",
"EDH-RSA-DES-CBC-SHA",
"DES-CBC-SHA" ]

class HealthCheck(FADC):

    def __init__(self, host, connector, verbose):
        self.prefix = "/system_health_check"
        super(HealthCheck, self).__init__(host, connector, verbose)

    def create(self, hc):
        errcodes = {-15}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, hc)
        if not ok:
            raise Exception('Create health_monitor failed')
        else:
            #update pool
            pool = RSpool(self.host, self.connector, self.verbose)
            _pool = pool.getone(hc.pool)
            if not _pool:
                raise Exception('Cannot get pool %s' %(hc.pool.id))

            hc.pool.health_check = "enable"
            hc.pool.health_check_list = _pool['health_check_list'] + " " + hc.id
            pool.update(None, hc.pool)

    def update(self, hc):
        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, hc)
        if not ok:
            raise Exception('Update health_monitor failed')
    def delete(self, hc):
        #detach pool
        pool = RSpool(self.host, self.connector, self.verbose)
        _pool = pool.getone(hc.pool)
        if not _pool:
            raise Exception('Cannot get pool %s' %(hc.pool.id))

        if hc.id in _pool['health_check_list']:
            hc.pool.health_check_list = _pool['health_check_list'].replace(hc.id,'')
        pool.health_check = _pool['health_check'] if len(hc.pool.health_check_list.replace(" ",'') if hasattr(hc.pool,'health_check_list') else "") else "disable"
        ok = pool.update(None, hc.pool)

        errcodes = {}
        ok = self.action_handler(sys._getframe().f_code.co_name, errcodes, hc)
        if not ok:
            raise f_exceptions.NotFoundException('Delete health_monitor failed')
            #raise Exception('Delete health_monitor failed')

    def getall(self):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes)
    def getone(self, hc):
        errcodes = {}
        return self.action_handler(sys._getframe().f_code.co_name, errcodes, hc)

    def mapping(self, hc):
        return {
            'mkey' :    hc.id,
            'type': hc.fadc_type,
            'interval':   str(hc.delay),
            'timeout': str(hc.timeout),
            'up_retry':    str(hc.max_retries),
            'port': hc.fadc_port,
            'send_string': str(hc.url_path),
            'status_code': str(hc.expected_codes),
            'method_type': hc.fadc_method_type,
        }

    def attrs_set_on_device(self):
        return {
            'down_retry':  "1",
            'dest_addr_type':  "ipv4",
            'dest_addr':   "0.0.0.0",
            'dest_addr6':  "::",
            'receive_string':  "receive-string",
            'match_type':  "match_string",
            'addr_type':   "ipv4",
            'host_addr6':  "::",
            'username':    "",
            'password':    "",
            'pwd_type':    "user-password",
            'folder':  "INBOX",
            'file':    "welcome.txt",
            'passive': "enable",
            'cpu': "96",
            'mem': "96",
            'disk':    "96",
            'agent-type':  "UCD",
            'version': "v1",
            'http_connect':    "no_connect",
            'hostname':    "",
            'compare-type':    "less",
            'cpu-weight':  "100",
            'mem-weight':  "100",
            'disk-weight': "100",
            'sip_request_type':    "register",
            'allow-ssl-version':   allow_ssl_version,
            'ssl-ciphers': ssl_ciphers,
            'local-cert':  "",
            'rtsp-method-type':    "options",
            'mysql-server-type':   "master",
            'radius-reject':   "disable",
        }


