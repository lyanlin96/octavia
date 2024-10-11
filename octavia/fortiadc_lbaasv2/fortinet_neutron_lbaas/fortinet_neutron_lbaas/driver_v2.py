
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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import importutils
from oslo_config import cfg
from neutron.services import provider_configuration as provconf
from neutron_lbaas.services.loadbalancer import constants as lb_constants
from neutron_lbaas.extensions import lbaas_agentschedulerv2

from fortinet_neutron_lbaas import agent_rpc
from fortinet_neutron_lbaas import plugin_rpc
from fortinet_neutron_lbaas import constants as agent_constants


LOG = logging.getLogger(__name__)


LB_SCHEDULERS = 'loadbalancer_schedulers'

AGENT_SCHEDULER_OPTS = [
    cfg.StrOpt('loadbalancer_scheduler_driver',
               default='neutron_lbaas.agent_scheduler.ChanceScheduler',
               help=_('Driver to use for scheduling '
                      'to a default loadbalancer agent')),
]

cfg.CONF.register_opts(AGENT_SCHEDULER_OPTS)


class FortinetLoadBalancerV2(object):
    '''Fortinet LoadBalancer V2.'''

    def __init__(self, plugin=None, env=None):
        """Driver initialization."""
        LOG.debug('FortinetLoadBalancerV2 1234')

        if not plugin:
            LOG.error('Required LBaaS Driver and Core Driver Missing')
            sys.exit(1)

        self.plugin = plugin
        self.env = env
        self.agent_rpc = agent_rpc.LbaasV2AgentRpc(
            agent_constants.TOPIC_LOADBALANCER_AGENT_V2
        )

        self.plugin_rpc = plugin_rpc.LBaaSv2PluginCallbacksRPC(self)

        self.loadbalancer = LoadBalancerManager(self)
        self.listener = ListenerManager(self)
        self.pool = PoolManager(self)
        self.member = MemberManager(self)
        self.healthmonitor = HealthMonitorManager(self)


        # Setting this on the db because the plugin no longer inherts from
        # database classes, the db does.
        self.plugin.db.agent_notifiers.update(
            {lb_constants.AGENT_TYPE_LOADBALANCERV2: self.agent_rpc})

        lb_sched_driver = provconf.get_provider_driver_class(
            cfg.CONF.loadbalancer_scheduler_driver, LB_SCHEDULERS)
        self.loadbalancer_scheduler = importutils.import_object(
            lb_sched_driver)

    def get_loadbalancer_agent(self, context, loadbalancer_id):
        agent = self.plugin.db.get_agent_hosting_loadbalancer(
            context, loadbalancer_id)
        if not agent:
            raise lbaas_agentschedulerv2.NoActiveLbaasAgent(
                loadbalancer_id=loadbalancer_id)
        return agent['agent']



class EntityManager(object):
    '''Parent for all managers defined in this module.'''

    def __init__(self, driver):
        self.driver = driver
        self.api_dict = None
        self.loadbalancer = None
        self.host = 'ubuntu-s'
        self.host = None

    def _call_rpc(self, context, entity, rpc_method):
        '''Perform operations common to create and delete for managers.'''

        try:
            agent_host, service = self._setup_crud(context, entity)
            rpc_callable = getattr(self.driver.agent_rpc, rpc_method)
            rpc_callable(context, self.api_dict, service, agent_host)
        except (lbaas_agentschedulerv2.NoEligibleLbaasAgent,
                lbaas_agentschedulerv2.NoActiveLbaasAgent) as e:
            LOG.error("Exception: %s: %s" % (rpc_method, e))
        except Exception as e:
            LOG.error("Exception: %s: %s" % (rpc_method, e))
            raise e



class LoadBalancerManager(EntityManager):

    @log_helpers.log_method_call
    def create(self, context, loadbalancer):
        """Create a loadbalancer."""

        self.device_driver = agent_constants.DRIVER_NAME
        agent = self.driver.loadbalancer_scheduler.schedule(
            self.driver.plugin, context, loadbalancer,
            self.device_driver)
        if not agent:
            raise lbaas_agentschedulerv2.NoEligibleLbaasAgent(
                loadbalancer_id=loadbalancer.id)

        self.driver.agent_rpc.create_loadbalancer(
            context, loadbalancer.to_dict(), agent['host'])

    @log_helpers.log_method_call
    def update(self, context, old_loadbalancer, loadbalancer):
        """Update a loadbalancer."""

        agent = self.driver.get_loadbalancer_agent(context, loadbalancer.id)
        if agent:
            self.driver.agent_rpc.update_loadbalancer(
                context,
                old_loadbalancer.to_dict(),
                loadbalancer.to_dict(),
                agent['host']
        )

    @log_helpers.log_method_call
    def delete(self, context, loadbalancer):
        """Delete a loadbalancer."""

        agent = self.driver.get_loadbalancer_agent(context, loadbalancer.id)
        if agent:
            self.driver.agent_rpc.delete_loadbalancer(
                context, loadbalancer.to_dict(), agent['host'])

    @log_helpers.log_method_call
    def refresh(self, context, loadbalancer):
        """Refresh a loadbalancer."""
        pass

    @log_helpers.log_method_call
    def stats(self, context, loadbalancer):
        """Get the statistic of loadbalancer."""

        return self.driver.plugin.db.stats(context, loadbalancer.id)



class ListenerManager(EntityManager):
    """ListenerManager class handles Neutron LBaaS listener CRUD."""

    @log_helpers.log_method_call
    def create(self, context, listener):
        """Create a listener."""

        agent = self.driver.get_loadbalancer_agent(context, listener.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.create_listener(
                context, listener.to_dict(), agent['host'])

    @log_helpers.log_method_call
    def update(self, context, old_listener, listener):
        """Update a listener."""

        agent = self.driver.get_loadbalancer_agent(context, listener.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.update_listener(
                context,
                old_listener.to_dict(),
                listener.to_dict(),
                agent['host']
            )

    @log_helpers.log_method_call
    def delete(self, context, listener):
        """Delete a listener."""

        agent = self.driver.get_loadbalancer_agent(context, listener.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.delete_listener(
                context, listener.to_dict(), agent['host'])



class PoolManager(EntityManager):
    """PoolManager class handles Neutron LBaaS pool CRUD."""

    @log_helpers.log_method_call
    def create(self, context, pool):
        """Create a listener."""

        agent = self.driver.get_loadbalancer_agent(context, pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.create_pool(
                context, pool.to_dict(), agent['host'])

    @log_helpers.log_method_call
    def update(self, context, old_pool, pool):
        """Update a listener."""

        agent = self.driver.get_loadbalancer_agent(context, pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.update_pool(
                context,
                old_pool.to_dict(),
                pool.to_dict(),
                agent['host']
            )

    @log_helpers.log_method_call
    def delete(self, context, pool):
        """Delete a listener."""

        agent = self.driver.get_loadbalancer_agent(context, pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.delete_pool(
                context, pool.to_dict(), agent['host'])



class MemberManager(EntityManager):
    """MemberManager class handles Neutron LBaaS pool member CRUD."""

    @log_helpers.log_method_call
    def create(self, context, member):
        """Create a listener."""

        agent = self.driver.get_loadbalancer_agent(context, member.pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.create_member(
                context, member.to_dict(), agent['host'])

    @log_helpers.log_method_call
    def update(self, context, old_member, member):
        """Update a listener."""

        agent = self.driver.get_loadbalancer_agent(context, member.pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.update_member(
                context,
                old_member.to_dict(),
                member.to_dict(),
                agent['host']
            )

    @log_helpers.log_method_call
    def delete(self, context, member):
        """Delete a listener."""

        agent = self.driver.get_loadbalancer_agent(context, member.pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.delete_member(
                context, member.to_dict(), agent['host'])



class HealthMonitorManager(EntityManager):
    """HealthMonitorManager class handles Neutron LBaaS monitor CRUD."""

    @log_helpers.log_method_call
    def create(self, context, healthmonitor):
        """Create a healthmonitor."""

        agent = self.driver.get_loadbalancer_agent(context, healthmonitor.pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.create_healthmonitor(
                context, healthmonitor.to_dict(), agent['host'])

    @log_helpers.log_method_call
    def update(self, context, old_healthmonitor, healthmonitor):
        """Update a healthmonitor."""

        agent = self.driver.get_loadbalancer_agent(context, healthmonitor.pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.update_healthmonitor(
                context,
                old_healthmonitor.to_dict(),
                healthmonitor.to_dict(),
                agent['host']
            )

    @log_helpers.log_method_call
    def delete(self, context, healthmonitor):
        """Delete a healthmonitor."""

        agent = self.driver.get_loadbalancer_agent(context, healthmonitor.pool.loadbalancer.id)
        if agent:
            self.driver.agent_rpc.delete_healthmonitor(
                context, healthmonitor.to_dict(), agent['host'])

