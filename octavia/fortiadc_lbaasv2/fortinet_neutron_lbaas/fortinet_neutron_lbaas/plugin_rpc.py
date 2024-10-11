
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

import oslo_messaging as messaging
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from neutron.db import agents_db
from neutron_lib import constants
from neutron_lbaas.db.loadbalancer import loadbalancer_dbv2
from neutron.common import rpc as n_rpc
from neutron_lbaas.drivers.common import agent_callbacks

from fortinet_neutron_lbaas import constants as agent_constants

LOG = logging.getLogger(__name__)

class LBaaSv2PluginCallbacksRPC(agent_callbacks.LoadBalancerCallbacks):
    """Agent to plugin RPC API."""

    target = messaging.Target(version='1.0')

    def __init__(self, driver=None):
        """LBaaSv2PluginCallbacksRPC constructor."""
        super(LBaaSv2PluginCallbacksRPC, self).__init__(driver.plugin)
        self.driver = driver


    def start_rpc_listeners(self):
        # call start_rpc_listeners after core_plugin add this driver to create RpcWorker.
        topic = agent_constants.TOPIC_LOADBALANCER_PLUGIN_V2
        self.conn = n_rpc.create_connection()
        self.conn.create_consumer(
            topic,
            [self,
             agents_db.AgentExtRpcCallback(self.driver.plugin.db)],
            fanout=False)
        self.conn.consume_in_threads()


    def get_error_devices(self, context, host=None):
        with context.session.begin(subtransactions=True):
            agents = self.plugin.db.get_lbaas_agents(
                context, filters={'host': [host]})
            if not agents:
                return []
            elif len(agents) > 1:
                LOG.warning('Multiple lbaas agents found on host %s', host)
            loadbalancers = self.plugin.db.list_loadbalancers_on_lbaas_agent(
                context, agents[0].id)
            loadbalancer_ids = [
                l.id for l in loadbalancers]

            qry = context.session.query(
                loadbalancer_dbv2.models.LoadBalancer.id)
            qry = qry.filter(
                loadbalancer_dbv2.models.LoadBalancer.id.in_(
                    loadbalancer_ids))
            qry = qry.filter(
                loadbalancer_dbv2.models.LoadBalancer.provisioning_status.in_(
                    [constants.ERROR]))
            up = True  # makes pep8 and sqlalchemy happy
            qry = qry.filter(
                loadbalancer_dbv2.models.LoadBalancer.admin_state_up == up)
            return [id for id, in qry]

    def get_pending_delete_devices(self, context, host=None):
        with context.session.begin(subtransactions=True):
            agents = self.plugin.db.get_lbaas_agents(
                context, filters={'host': [host]})
            if not agents:
                return []
            elif len(agents) > 1:
                LOG.warning('Multiple lbaas agents found on host %s', host)
            loadbalancers = self.plugin.db.list_loadbalancers_on_lbaas_agent(
                context, agents[0].id)
            loadbalancer_ids = [
                l.id for l in loadbalancers]

            qry = context.session.query(
                loadbalancer_dbv2.models.LoadBalancer.id)
            qry = qry.filter(
                loadbalancer_dbv2.models.LoadBalancer.id.in_(
                    loadbalancer_ids))
            qry = qry.filter(
                loadbalancer_dbv2.models.LoadBalancer.provisioning_status.in_(
                    [constants.PENDING_DELETE]))
            up = True  # makes pep8 and sqlalchemy happy
            qry = qry.filter(
                loadbalancer_dbv2.models.LoadBalancer.admin_state_up == up)
            return [id for id, in qry]

    @log_helpers.log_method_call
    def loadbalancer_destroyed(self, context, loadbalancer_id=None):
        """Agent confirmation hook that loadbalancer has been destroyed."""
        self.driver.plugin.db.delete_loadbalancer(context, loadbalancer_id)


    @log_helpers.log_method_call
    def listener_destroyed(self, context, listener_id=None):
        """Agent confirmation hook that listener has been destroyed."""
        self.driver.plugin.db.delete_listener(context, listener_id)

    @log_helpers.log_method_call
    def pool_destroyed(self, context, pool_id=None):
        """Agent confirmation hook that pool has been destroyed."""
        self.driver.plugin.db.delete_pool(context, pool_id)

    @log_helpers.log_method_call
    def member_destroyed(self, context, member_id=None):
        """Agent confirmation hook that member has been destroyed."""
        self.driver.plugin.db.delete_member(context, member_id)

    @log_helpers.log_method_call
    def healthmonitor_destroyed(self, context, healthmonitor_id=None):
        """Agent confirmation hook that healthmonitor has been destroyed."""
        self.driver.plugin.db.delete_healthmonitor(context, healthmonitor_id)

