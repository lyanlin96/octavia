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

import json
from oslo_config import cfg
from oslo_log import log as logging

from fadc_octavia_provider.fortiadc_agent.servicemanager.lb import LoadBalancer
from fadc_octavia_provider.fortiadc_agent.servicemanager.connector import Connector
from fadc_octavia_provider.fortiadc_agent.servicemanager.listener import Listener
from fadc_octavia_provider.fortiadc_agent.servicemanager.pool import Pool
from fadc_octavia_provider.fortiadc_agent.servicemanager.member import Member
from fadc_octavia_provider.fortiadc_agent.servicemanager.health_monitor import HealthMonitor

LOG = logging.getLogger(__name__)

class FadcDevice:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            '''
            if isinstance(value, dict):
                setattr(self, key, FadcDevice(**value))
            elif isinstance(value, list):
                setattr(self, key, [FadcDevice(**item) if isinstance(item, dict) else item for item in value])
            else:
                setattr(self, key, value)
            '''
            setattr(self, key, value)

class FadcdeviceDriver(object):
    def __init__(self, conf, project_id = None):
        self.conf = conf
        self.o_device = FadcDevice(**conf.d_projects[project_id])
        self.host = self.o_device.fadc_FQDN
        self.plugin_rpc = None
        self.conn()
        #print(self.conf.d_projects)

    def get_name(self):
        return self.__class__.__name__

    def disconnect(self):
        self.connector.logout()

    def conn(self):
        if hasattr(self, "connector"):
            self.disconnect()
        self.connector = Connector(self.host, self.o_device.certificate_verify, self.o_device.ca_file)
        try:
            self.connector.login(self.o_device.fadc_username, self.o_device.fadc_password)
            #self.connector.check_version()
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
        LOG.info("inconsistent, deploy_instance!")
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


