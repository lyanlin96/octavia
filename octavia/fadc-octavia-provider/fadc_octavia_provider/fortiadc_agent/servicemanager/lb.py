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
from fadc_octavia_provider.fortiadc_agent.servicemanager.listener import Listener
from fadc_octavia_provider.fortiadc_agent.fadc_api.vdom import Vdom
from fadc_octavia_provider.fortiadc_agent.fadc_api.network import Interface
from fadc_octavia_provider.fortiadc_agent.fadc_api.network import Routing
from fadc_octavia_provider.fortiadc_agent.fadc_api.network import Nat_pool
from fadc_octavia_provider.fortiadc_agent.fadc_network_driver import FadcNetworkDriver 
from oslo_log import log as logging
#from neutron_lbaas.services.loadbalancer import constants as lb_const
from octavia.common import constants as lb_const
#from neutron_lbaas.services.loadbalancer import data_models

LOG = logging.getLogger(__name__)

class LoadBalancer(object):

    def __init__(self, fadc_driver):
        self.fadc = fadc_driver
        self.connector = self.fadc.connector
        self.vdom = Vdom(self.fadc.host, self.connector,self.fadc.conf.debug_mode)

    def create(self, lb):
        LOG.debug("create Vdom, %s", lb)
        self.vdom.create(lb.project_id)
        LOG.debug("Map network interface to vdom %s" %(lb.project_id))
        intf = Interface(self.fadc.host, self.connector, self.fadc.conf.debug_mode)
        intf.attach_vdom(lb.project_id, self.fadc.o_device.fadc_vdom_network_mapping, self.fadc.o_device.fadc_vdom_network_ip)
        intf.set_allowaccess(self.fadc.o_device.fadc_vdom_network_allowAccess)
        route = Routing(self.fadc.host, self.connector, self.fadc.conf.debug_mode)
        route.create(self.fadc.o_device.fadc_vdom_default_gw, lb.project_id)
        network_driver = FadcNetworkDriver()
        network_driver.plug_vip_to_port(lb.vip.ip_address, self.fadc.o_device.fadc_bind_vip_port_id)

    def delete(self, lb):
        LOG.debug("delete vdom")
        LOG.debug("map network back to root")
        nat_pool = Nat_pool(self.fadc.host, self.connector, self.fadc.conf.debug_mode)
        nat_pool.delete(self.fadc.o_device.fadc_vdom_network_mapping, lb.project_id)
        intf = Interface(self.fadc.host, self.connector, self.fadc.conf.debug_mode)
        intf.detach_vdom(lb.project_id)
        route = Routing(self.fadc.host, self.connector, self.fadc.conf.debug_mode)
        route.delete(self.fadc.o_device.fadc_vdom_default_gw, lb.project_id)
        self.vdom.delete(lb.project_id)

    def unplug(self, lb):
        LOG.debug("unplug %s", lb)
        network_driver = FadcNetworkDriver()
        try:
            network_driver.unplug_vip_from_port(lb['vip_address'], self.fadc.o_device.fadc_bind_vip_port_id)
        except Exception as e:
            LOG.error("Error unplug vip: %s", e.message)

    def get_stats(self, lb):
        lb_stats = {}
        try:
            #check if vdom exist
            if not self.vdom.is_exist(lb.project_id):
                raise Exception('Vdom not exist')
            listener = Listener(self.fadc)
            vs_stats = listener.get_stats([data_models.Listener.from_dict(pool.listener) for pool in lb.pools if pool.listener])

            # convert to bytes
            lb_stats[lb_const.STATS_IN_BYTES] = \
                vs_stats['bytesIn']
            lb_stats[lb_const.STATS_OUT_BYTES] = \
                vs_stats['bytesOut']
            lb_stats[lb_const.STATS_ACTIVE_CONNECTIONS] = \
                vs_stats['curConns']
            lb_stats[lb_const.STATS_TOTAL_CONNECTIONS] = \
                vs_stats['totConns']

            #for k,v in lb_stats.iteritems():
            #    print(k, v)
        except Exception as e:
            LOG.error("Error getting loadbalancer stats: %s", e.message)

        finally:
            return lb_stats



