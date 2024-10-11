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

import cotyledon
import time
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_messaging.rpc import dispatcher
from oslo_utils import uuidutils

from octavia.common import constants
from octavia.common import rpc
from fadc_octavia_provider.fortiadc_agent import endpoints

from octavia.db import api as db_apis
from octavia.db import repositories as repo
from octavia_lib.api.drivers import driver_lib
from octavia_lib.api.drivers import exceptions as driver_exceptions
from octavia_lib.common import constants as lib_consts
from fadc_octavia_provider.fortiadc_agent.fadc_device_driver import FadcdeviceDriver


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class UpdateService(cotyledon.Service):

    def __init__(self, worker_id, conf):
        super().__init__(worker_id)
        self._lb_repo = repo.LoadBalancerRepository()
        self.running = True
        self.conf = conf
        LOG.debug('UpdateService init')
        self.target = messaging.Target(
            namespace=constants.RPC_NAMESPACE_CONTROLLER_AGENT,
            topic='fortiadc_octavia_topic', version='2.0', fanout=False
        )
        self.client = rpc.get_client(self.target)

        self.driver_lib = driver_lib.DriverLibrary(
            status_socket=CONF.driver_agent.status_socket_path,
            stats_socket=CONF.driver_agent.stats_socket_path,
            get_socket=CONF.driver_agent.get_socket_path,
        )

    def run(self):
        while self.running:
            #self.periodic_task()
            time.sleep(600)

    def terminate(self):
        LOG.debug('Stopping UpdateService...')
        self.running = False 
        super().terminate()

    def periodic_task(self):
        LOG.debug('UpdateService periodic_task') 
        self.update_state()

    def update_state(self):
        _lb_list, _ = self._lb_repo.get_all(db_apis.get_session(), operating_status='OFFLINE', provisioning_status='ACTIVE', provider='fortiadc_driver')
        for lb in _lb_list:
            lb_status = {constants.LOADBALANCERS: [{'id': lb.id}]}
            lb_status[constants.LOADBALANCERS][0][lib_consts.OPERATING_STATUS] = lib_consts.ONLINE
            listeners_status = []
            pools_status = []
            members_status = []

            lb_status['listeners'] = listeners_status
            lb_status['pools'] = pools_status
            lb_status['members'] = members_status

            if lb.listeners:
                for listener in lb.listeners:
                    listeners_status.append({'id': listener.id, lib_consts.OPERATING_STATUS: lib_consts.ONLINE})
            if lb.pools:
                for pool in lb.pools:
                    pools_status.append({'id': pool.id, lib_consts.OPERATING_STATUS: lib_consts.ONLINE})
                    for member in pool.members:
                        members_status.append({'id': member.id, lib_consts.OPERATING_STATUS: lib_consts.ONLINE})

            self.driver_lib.update_loadbalancer_status(lb_status)
