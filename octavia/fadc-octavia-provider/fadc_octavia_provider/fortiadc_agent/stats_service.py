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

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class StatsService(cotyledon.Service):

    def __init__(self, worker_id, conf):
        super().__init__(worker_id)
        self.running = True
        self.conf = conf
        LOG.debug('StatsService init')
        self.target = messaging.Target(
            namespace=constants.RPC_NAMESPACE_CONTROLLER_AGENT,
            topic='fortiadc_octavia_topic', version='2.0', fanout=False
        )
        self.client = rpc.get_client(self.target)

    def run(self):
        while self.running:
            time.sleep(600)
            self.periodic_task()

    def terminate(self):
        LOG.debug('Stopping StatsService...')
        self.running = False 
        super().terminate()

    def periodic_task(self):
        LOG.debug("Stats service sync stats")
        payload = {'name': 'sync_stats'}
        self.client.cast({}, 'sync_stats', **payload)
