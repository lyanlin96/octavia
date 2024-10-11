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

import ipaddress
import time

from neutronclient.common import exceptions as neutron_client_exceptions
from novaclient import exceptions as nova_client_exceptions
from octavia_lib.common import constants as lib_consts
from oslo_config import cfg
from oslo_log import log as logging

from octavia.common import constants
from octavia.common import data_models
from octavia.common import exceptions
from octavia.common import utils as common_utils
from octavia.common import clients
from octavia.i18n import _
from octavia.network import base
from octavia.network import data_models as n_data_models
from octavia.network.drivers.neutron import base as neutron_base
from octavia.network.drivers.neutron import utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

class FadcNetworkManager():
    def __init__(self):
        LOG.debug('FadcNetworkManager init')
        self.neutron_client = clients.NeutronAuth.get_neutron_client(
            #endpoint=CONF.neutron.endpoint,
            #region=CONF.neutron.region_name,
            #endpoint_type=CONF.neutron.endpoint_type,
            #service_name=CONF.neutron.service_name,
            #insecure=CONF.neutron.insecure,
            #ca_cert=CONF.neutron.ca_certificates_file
        )

    def plug_vip_to_port(self, vip, port_id):
        try:
            self._add_vip_to_port(vip, port_id)
        except neutron_client_exceptions.PortNotFoundClient as e:
            raise base.PortNotFound(str(e))
        except Exception as e:
            message = _('Error adding allowed address pair(s) {ips} '
                        'to port {port_id}.').format(ips=vip,
                                                     port_id=port_id)
            LOG.exception(message)
            raise base.PlugVIPException(message) from e

    def _no_exist(self, vip, ip_list):
        for ip in ip_list:
            if ip['ip_address'] == vip:
                return False
        return True

    def _add_vip_to_port(self, vip, port_id):
        LOG.debug('add_vip_to_port %s %s', vip, port_id)
        port_obj = self.neutron_client.show_port(port_id)
        ip_list = port_obj['port']['allowed_address_pairs']
        if isinstance(vip, list):
            for ip in vip:
                if self._no_exist(ip, ip_list):
                    ip_list.append({'ip_address': ip})
        else:
            if self._no_exist(vip, ip_list):
                ip_list.append({'ip_address': vip})
            else:
                return
        print(ip_list)
        aap_info = {
            'port': {
                'allowed_address_pairs': ip_list
            }
        }
        self.neutron_client.update_port(port_id, aap_info)

    def unplug_vip_from_port(self, vip, port_id):
        try:
            self._remove_vip_from_port(vip, port_id)
        except neutron_client_exceptions.PortNotFoundClient as e:
            raise base.PortNotFound(str(e))
        except Exception as e:
            message = _('Error adding allowed address pair(s) {ips} '
                        'to port {port_id}.').format(ips=vip,
                                                     port_id=port_id)
            LOG.exception(message)
            raise base.PlugVIPException(message) from e
        
    def _remove_vip_from_port(self, vip, port_id):
        LOG.debug('remove_vip_from_port %s %s', vip, port_id)
        port_obj = self.neutron_client.show_port(port_id)
        ip_list = port_obj['port']['allowed_address_pairs']
        for ip in reversed(ip_list):
            if ip['ip_address'] == vip:
                ip_list.remove(ip)
        print(ip_list)
        aap_info = {
            'port': {
                'allowed_address_pairs': ip_list
            }
        }
        self.neutron_client.update_port(port_id, aap_info)
