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

from fadc_octavia_provider.fortiadc_agent.fadc_api.slb.virtual_server import VirtualServer
from fadc_octavia_provider.fortiadc_agent.fadc_api.network import Nat_pool
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

class Listener(object):

    def __init__(self, fadc_driver):
        self.conf = fadc_driver.conf
        self.o_device = fadc_driver.o_device
        self.host = fadc_driver.host
        self.connector = fadc_driver.connector
        self.vs = VirtualServer(self.host, self.connector, self.conf.debug_mode)
        self.profile = {
            "HTTP" : "LB_PROF_HTTP",
            "HTTPS" : "LB_PROF_HTTPS",
            "TERMINATED_HTTPS" : "LB_PROF_HTTPS",
            "TCP" : "LB_PROF_TCP",
        }
        self.method = {
            "ROUND_ROBIN" : "LB_METHOD_ROUND_ROBIN",
            "LEAST_CONNECTIONS" : "LB_METHOD_LEAST_CONNECTION",
            "SOURCE_IP" : "LB_METHOD_ROUND_ROBIN"
        }
        self.vstype = {
            "HTTP" : "l7-load-balance",
            "HTTPS" : "l7-load-balance",
            "TCP" : "l4-load-balance"
        }

    def create(self, listener):
        _pool = listener.default_pool
        if not _pool:
            LOG.warning("No pool information.")
        else:
            try:
                self.check_parameter(listener)
                if listener.fadc_pktfwd != '' and listener.fadc_nat_pool and listener.protocol == 'TCP':
                    LOG.debug("create nat pool")
                    nat_pool = Nat_pool(self.host, self.connector, self.conf.debug_mode)
                    nat_pool.create(listener.fadc_nat_pool, listener.fadc_vs_nat_intf, listener.project_id)
                    listener.fadc_nat_pool_name = "openstack_lbaas"
                LOG.debug("create listener")
                self.vs.create(listener)
            except:
                raise Exception("Create listener failed")

    def update(self, listener):
        _pool = listener.default_pool
        if not _pool:
            LOG.warning("No pool information.")
        else:
            try:
                self.check_parameter(listener)
                LOG.debug("update listener")
                self.vs.update(listener)
            except:
                raise Exception("update listener failed")

    def delete(self, listener):
        LOG.debug("delete listener")
        self.vs.delete(listener)

    def get_stats(self, listeners):
        return self.vs.get_all_vs_stats(listeners, self.o_device.fadc_get_stats_interval)

    def get_status(self, listener):
        return self.vs.getstatus(listener)

    def check_parameter(self, listener):

        listener.fadc_pktfwd = self.o_device.fadc_vs_packet_forward_method
        listener.fadc_nat_pool = self.o_device.fadc_vs_nat_pool
        listener.fadc_vs_nat_intf = self.o_device.fadc_vs_nat_intf
        listener.fadc_persistence = self.o_device.fadc_vs_persistency
        listener.fadc_dev_intf = self.o_device.fadc_vs_dev_intf
        listener.fadc_status = "enable"
        listener.vs_type = self.vstype.get(listener.protocol)
        if listener.connection_limit == -1:
            listener.fadc_connection_limit = 0
        else:
            listener.fadc_connection_limit = listener.connection_limit
        if not bool(listener.enabled):
            listener.fadc_status = "disable"
        listener.fadc_pool_id = listener.default_pool.id
        listener.fadc_profile = self.profile.get(listener.protocol)
        listener.fadc_method = self.method.get(listener.default_pool.lb_algorithm)
        listener.fadc_client_ssl_prof = "LB_CLIENT_SSL_PROF_DEFAULT" if listener.protocol == "HTTPS" else ""

