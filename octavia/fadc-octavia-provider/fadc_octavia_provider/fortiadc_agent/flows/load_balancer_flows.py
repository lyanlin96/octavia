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

from oslo_config import cfg
from oslo_log import log as logging
from taskflow.patterns import linear_flow
from taskflow.patterns import unordered_flow

from octavia.common import constants
from octavia.common import exceptions
from octavia.common import utils
from fadc_octavia_provider.fortiadc_agent.flows import listener_flows
from fadc_octavia_provider.fortiadc_agent.flows import member_flows
from fadc_octavia_provider.fortiadc_agent.flows import pool_flows
from octavia.controller.worker.v2.tasks import database_tasks as fadc_database_tasks
from octavia.controller.worker.v2.tasks import lifecycle_tasks as fadc_lifecycle_tasks
from fadc_octavia_provider.fortiadc_agent.tasks import fortiadc_driver_tasks
from octavia.controller.worker.v2.tasks import notification_tasks
from octavia.db import repositories as repo

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class LoadBalancerFlows(object):

    def __init__(self):
        self.listener_flows = listener_flows.ListenerFlows()
        self.pool_flows = pool_flows.PoolFlows()
        self.member_flows = member_flows.MemberFlows()
        self.lb_repo = repo.LoadBalancerRepository()

    def get_create_load_balancer_flow(self, topology, listeners=None):
        LOG.info('get_create_load_balancer_flow')
        f_name = constants.CREATE_LOADBALANCER_FLOW
        lb_create_flow = linear_flow.Flow(f_name)

        lb_create_flow.add(fadc_lifecycle_tasks.LoadBalancerIDToErrorOnRevertTask(
            requires=constants.LOADBALANCER_ID))

        # allocate VIP
        lb_create_flow.add(fadc_database_tasks.ReloadLoadBalancer(
            name=constants.RELOAD_LB_BEFOR_ALLOCATE_VIP,
            requires=constants.LOADBALANCER_ID,
            provides=constants.LOADBALANCER
        ))

        lb_create_flow.add(fortiadc_driver_tasks.LoadBalancerCreate(
            name='fortiadc_loadbalancer_create',
            requires=constants.LOADBALANCER
        ))

        #if listeners:
        #    lb_create_flow.add(*self._create_listeners_flow())

        lb_create_flow.add(
            fadc_database_tasks.MarkLBActiveInDB(
                mark_subobjects=True,
                requires=constants.LOADBALANCER
            )
        )

        if CONF.controller_worker.event_notifications:
            LOG.info('create event_notifications')
            lb_create_flow.add(
                notification_tasks.SendCreateNotification(
                    requires=constants.LOADBALANCER
                )
            )

        LOG.info('get_create_load_balancer_flow end')

        return lb_create_flow

    def _create_listeners_flow(self):
        LOG.info('get_create_listeners_flow')
        flows = []
        flows.append(
            fadc_database_tasks.ReloadLoadBalancer(
                name=constants.RELOAD_LB_AFTER_AMP_ASSOC_FULL_GRAPH,
                requires=constants.LOADBALANCER_ID,
                provides=constants.LOADBALANCER
            )
        )
        flows.append(
            self.listener_flows.get_create_all_listeners_flow()
        )
        flows.append(
            fadc_database_tasks.MarkLBActiveInDB(
                mark_subobjects=True,
                requires=constants.LOADBALANCER
            )
        )
        return flows

    def _get_delete_listeners_flow(self, listeners):
        """Sets up an internal delete flow

        :param listeners: A list of listener dicts
        :return: The flow for the deletion
        """
        listeners_delete_flow = unordered_flow.Flow('listeners_delete_flow')
        for listener in listeners:
            listeners_delete_flow.add(
                self.listener_flows.get_delete_listener_internal_flow(
                    listener))
        return listeners_delete_flow

    def get_delete_load_balancer_flow(self, lb):
        """Creates a flow to delete a load balancer.

        :returns: The flow for deleting a load balancer
        """
        LOG.info('get_delete_load_balancer_flow false')
        return self._get_delete_load_balancer_flow(lb, False)

    def _get_delete_pools_flow(self, pools):
        """Sets up an internal delete flow
        :param lb: load balancer
        :return: (flow, store) -- flow for the deletion and store with all
                    the listeners stored properly
        """
        pools_delete_flow = unordered_flow.Flow('pool_delete_flow')
        for pool in pools:
            pools_delete_flow.add(
                self.pool_flows.get_delete_pool_flow_internal(
                    pool[constants.POOL_ID]))
        return pools_delete_flow

    def _get_delete_load_balancer_flow(self, lb, cascade,
                                       listeners=(), pools=()):
        delete_LB_flow = linear_flow.Flow(constants.DELETE_LOADBALANCER_FLOW)
        delete_LB_flow.add(fadc_lifecycle_tasks.LoadBalancerToErrorOnRevertTask(
            requires=constants.LOADBALANCER))
        #delete_LB_flow.add(compute_tasks.NovaServerGroupDelete(
        #    requires=constants.SERVER_GROUP_ID))
        delete_LB_flow.add(fadc_database_tasks.MarkLBAmphoraeHealthBusy(
            requires=constants.LOADBALANCER))
        if cascade:
            listeners_delete = self._get_delete_listeners_flow(listeners)
            pools_delete = self._get_delete_pools_flow(pools)
            delete_LB_flow.add(listeners_delete)
            delete_LB_flow.add(pools_delete)
            #for pool in pools:
            #    members_delete = self.get_delete_member_flow(member)

        delete_LB_flow.add(fortiadc_driver_tasks.LoadBalancerUnplug(
            requires=constants.LOADBALANCER))
        delete_LB_flow.add(fadc_database_tasks.MarkLBAmphoraeDeletedInDB(
            requires=constants.LOADBALANCER))
        delete_LB_flow.add(fadc_database_tasks.DisableLBAmphoraeHealthMonitoring(
            requires=constants.LOADBALANCER))
        delete_LB_flow.add(fadc_database_tasks.MarkLBDeletedInDB(
            requires=constants.LOADBALANCER))
        delete_LB_flow.add(fadc_database_tasks.DecrementLoadBalancerQuota(
            requires=constants.PROJECT_ID))
        if CONF.controller_worker.event_notifications:
            delete_LB_flow.add(notification_tasks.SendDeleteNotification(
                requires=constants.LOADBALANCER))
        return delete_LB_flow

    def get_cascade_delete_load_balancer_flow(self, lb, listeners, pools):
        """Creates a flow to delete a load balancer.

        :returns: The flow for deleting a load balancer
        """
        LOG.info('get_cascade_delete_load_balancer_flow true')
        return self._get_delete_load_balancer_flow(lb, True,
                                                   listeners=listeners,
                                                   pools=pools)

    def get_update_load_balancer_flow(self):
        """Creates a flow to update a load balancer.

        :returns: The flow for update a load balancer
        """
        update_LB_flow = linear_flow.Flow(constants.UPDATE_LOADBALANCER_FLOW)
        update_LB_flow.add(fadc_lifecycle_tasks.LoadBalancerToErrorOnRevertTask(
            requires=constants.LOADBALANCER))
        update_LB_flow.add(fadc_database_tasks.UpdateLoadbalancerInDB(
            requires=[constants.LOADBALANCER, constants.UPDATE_DICT]))
        update_LB_flow.add(fadc_database_tasks.MarkLBActiveInDB(
            requires=constants.LOADBALANCER))
        if CONF.controller_worker.event_notifications:
            update_LB_flow.add(
                notification_tasks.SendUpdateNotification(
                    requires=constants.LOADBALANCER
                )
            )

        return update_LB_flow
