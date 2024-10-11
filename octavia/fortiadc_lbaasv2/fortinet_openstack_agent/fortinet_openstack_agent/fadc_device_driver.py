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

from neutron_lbaas.services.loadbalancer import data_models

from oslo_config import cfg
from oslo_log import log as logging

from fortinet_openstack_agent.servicemanager.lb import LoadBalancer
from fortinet_openstack_agent.servicemanager.connector import Connector
from fortinet_openstack_agent.servicemanager.listener import Listener
from fortinet_openstack_agent.servicemanager.pool import Pool
from fortinet_openstack_agent.servicemanager.member import Member
from fortinet_openstack_agent.servicemanager.health_monitor import HealthMonitor


OPTS = [
    cfg.StrOpt(
        'fadc_FQDN',
        default="10.0.100.85",
        help='FQDN or IP address of FortiADC device'
    ),
    cfg.StrOpt(
        'fadc_username', default='admin',
        help='User with privilege to access the Fortiadc device'
    ),
    cfg.StrOpt(
        'fadc_password', default='', secret=True,
        help='User password access the Fortiadc device'
    ),
    cfg.ListOpt(
        'fadc_vdom_network_mapping', default=['port5'],
        help='Map network to vdom interfaces'
    ),
    cfg.StrOpt(
        'fadc_vs_dev_intf', default='port5',
        help='Virtual server outgoing interface'
    ),
    cfg.StrOpt(
        'fadc_vs_persistency', default='',
        help='Virtual server persistency'
    ),
    cfg.StrOpt(
        'fadc_vs_packet_forward_method', default='',
        help='Virtual server packet forward method'
    ),
    cfg.StrOpt(
        'fadc_healthcheck_port', default='80',
        help='Health Check monitor port'
    ),
    cfg.StrOpt(
        'fadc_get_stats_interval', default='2',
        help='Set stats interval. 1hr/6hr/1day/1wk/1m/1y'
    ),
    cfg.BoolOpt(
        'debug_mode', default=True,
        help='Enable debug log message on device driver'
    ),
    cfg.DictOpt(
        'fadc_vdom_network_allowAccess', default={'port5':'http'}, secret=True,
        help='Virtual server packet forward method'
    ),
    cfg.DictOpt(
        'fadc_vdom_network_ip', default={'port5':'172.24.4.129/24'}, secret=True,
        help='port main ip address'
    ),
    cfg.StrOpt(
        'fadc_vdom_default_gw', default='172.24.4.1',
        help='Vdom default gateway'
    ),
    cfg.ListOpt(
        'fadc_vs_nat_pool', default=[],
        help='FullNAT pool range '
    ),
    cfg.StrOpt(
        'fadc_vs_nat_intf', default='port5',
        help='FullNAT pool interface'
    )
]



LOG = logging.getLogger(__name__)
class FadcdeviceDriver(object):
    def __init__(self, conf):
        self.conf = conf
        self.conf.register_opts(OPTS)
        self.host = self.conf.fadc_FQDN
        self.plugin_rpc = None
        self.conn()

    def get_name(self):
        return self.__class__.__name__

    def disconnect(self):
        self.connector.logout()

    def conn(self):
        if hasattr(self, "connector"):
            self.disconnect()
        self.connector = Connector(self.host)
        try:
            self.connector.login(self.conf.fadc_username, self.conf.fadc_password)
            self.connector.check_version()
        except Exception as e:
            LOG.error('login %s failed. reason %s\n' %(self.host, e))
    def refresh(self):
        try:
            #self.connector.refresh()
            self.conn()
        except Exception as e:
            LOG.error('refresh %s failed. reason %s\n' %(self.host, e))

    def remove_orphans(self, lb_ids):
        pass
    def deploy_instance(self, loadbalancer):
        LOG.warning("inconsistent!")
        self.loadbalancer.create(loadbalancer)
        for pool in loadbalancer.pools:
            self.pool.create(pool)
            if pool.listener:
                listener = data_models.Listener.from_dict(pool.listener)
                listener.default_pool = pool
                self.listener.create(listener)
            for member in pool.members:
                self.member.create(member)
            if pool.healthmonitor:
                self.healthmonitor.create(pool.healthmonitor)
    @property
    def loadbalancer(self):
        return LoadBalancer(self)

    @property
    def listener(self):
        return Listener(self)

    @property
    def pool(self):
        return Pool(self)

    @property
    def member(self):
        return Member(self)

    @property
    def healthmonitor(self):
        return HealthMonitor(self)


