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

from octavia.common import constants
from octavia.controller.worker.v2.tasks import database_tasks as fadc_database_tasks
from octavia.controller.worker.v2.tasks import lifecycle_tasks as fadc_lifecycle_tasks
from fadc_octavia_provider.fortiadc_agent.tasks import fortiadc_driver_tasks

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

class PoolFlows(object):

    def get_create_pool_flow(self):
        """Create a flow to create a pool

        :returns: The flow for creating a pool
        """
        create_pool_flow = linear_flow.Flow(constants.CREATE_POOL_FLOW)
        create_pool_flow.add(fadc_lifecycle_tasks.PoolToErrorOnRevertTask(
            requires=[constants.POOL_ID,
                      constants.LISTENERS,
                      constants.LOADBALANCER]))
        create_pool_flow.add(fadc_database_tasks.MarkPoolPendingCreateInDB(
            requires=constants.POOL_ID))

        create_pool_flow.add(fortiadc_driver_tasks.PoolCreate(
            requires=[constants.POOL_ID, constants.LISTENERS]
        ))
        create_pool_flow.add(fadc_database_tasks.MarkPoolActiveInDB(
            requires=constants.POOL_ID))
        create_pool_flow.add(fadc_database_tasks.MarkLBAndListenersActiveInDB(
            requires=(constants.LOADBALANCER_ID, constants.LISTENERS)))

        return create_pool_flow

    def get_delete_pool_flow(self):
        """Create a flow to delete a pool

        :returns: The flow for deleting a pool
        """
        delete_pool_flow = linear_flow.Flow(constants.DELETE_POOL_FLOW)
        delete_pool_flow.add(fadc_lifecycle_tasks.PoolToErrorOnRevertTask(
            requires=[constants.POOL_ID,
                      constants.LISTENERS,
                      constants.LOADBALANCER]))
        delete_pool_flow.add(fadc_database_tasks.MarkPoolPendingDeleteInDB(
            requires=constants.POOL_ID))
        delete_pool_flow.add(fadc_database_tasks.CountPoolChildrenForQuota(
            requires=constants.POOL_ID, provides=constants.POOL_CHILD_COUNT))
        delete_pool_flow.add(fortiadc_driver_tasks.PoolDelete(
            requires=constants.POOL_ID))
        delete_pool_flow.add(fadc_database_tasks.DeletePoolInDB(
            requires=constants.POOL_ID))
        delete_pool_flow.add(fadc_database_tasks.DecrementPoolQuota(
            requires=[constants.PROJECT_ID, constants.POOL_CHILD_COUNT]))
        delete_pool_flow.add(fadc_database_tasks.MarkLBAndListenersActiveInDB(
            requires=(constants.LOADBALANCER_ID, constants.LISTENERS)))

        return delete_pool_flow

    def get_delete_pool_flow_internal(self, pool_id):
        """Create a flow to delete a pool, etc.

        :returns: The flow for deleting a pool
        """
        delete_pool_flow = linear_flow.Flow(constants.DELETE_POOL_FLOW + '-' +
                                            pool_id)
        # health monitor should cascade
        # members should cascade
        delete_pool_flow.add(fadc_database_tasks.MarkPoolPendingDeleteInDB(
            name='mark_pool_pending_delete_in_db_' + pool_id,
            requires=constants.POOL_ID,
            inject={constants.POOL_ID: pool_id}))
        delete_pool_flow.add(fadc_database_tasks.CountPoolChildrenForQuota(
            name='count_pool_children_for_quota_' + pool_id,
            requires=constants.POOL_ID,
            provides=constants.POOL_CHILD_COUNT,
            inject={constants.POOL_ID: pool_id}))
        delete_pool_flow.add(fortiadc_driver_tasks.PoolDelete(
            name='delete_pool_in_adc_' + pool_id,
            requires=constants.POOL_ID,
            inject={constants.POOL_ID: pool_id}))
        delete_pool_flow.add(fadc_database_tasks.DeletePoolInDB(
            name='delete_pool_in_db_' + pool_id,
            requires=constants.POOL_ID,
            inject={constants.POOL_ID: pool_id}))
        delete_pool_flow.add(fadc_database_tasks.DecrementPoolQuota(
            name='decrement_pool_quota_' + pool_id,
            requires=[constants.PROJECT_ID, constants.POOL_CHILD_COUNT]))

        return delete_pool_flow

    def get_update_pool_flow(self):
        """Create a flow to update a pool

        :returns: The flow for updating a pool
        """
        update_pool_flow = linear_flow.Flow(constants.UPDATE_POOL_FLOW)
        update_pool_flow.add(fadc_lifecycle_tasks.PoolToErrorOnRevertTask(
            requires=[constants.POOL_ID,
                      constants.LISTENERS,
                      constants.LOADBALANCER]))
        update_pool_flow.add(fadc_database_tasks.MarkPoolPendingUpdateInDB(
            requires=constants.POOL_ID))
        #update_pool_flow.add(amphora_driver_tasks.ListenersUpdate(
        #    requires=constants.LOADBALANCER_ID))
        update_pool_flow.add(fortiadc_driver_tasks.PoolUpdate(
            requires=[constants.LISTENERS, constants.POOL_ID]))
        update_pool_flow.add(fadc_database_tasks.UpdatePoolInDB(
            requires=[constants.POOL_ID, constants.UPDATE_DICT]))
        update_pool_flow.add(fadc_database_tasks.MarkPoolActiveInDB(
            requires=constants.POOL_ID))
        update_pool_flow.add(fadc_database_tasks.MarkLBAndListenersActiveInDB(
            requires=(constants.LOADBALANCER_ID, constants.LISTENERS)))

        return update_pool_flow

    def get_delete_pools_member_health_flow(self, pools):
        """Create a flow to update a pool

        :returns: The flow for updating a pool
        """
        delete_pools_member_health_flow = linear_flow.Flow('fortiadc-delete-pools-member-health-flow')
        for pool in pools:
            '''
            for member in pool.members:
                dict_member = member.to_dict()
                dict_member[constants.MEMBER_ID] = member.id
                LOG.info('delete member %s', member.id)
                delete_pools_member_health_flow.add(fortiadc_driver_tasks.MemberDeleteObj(
                    requires=constants.MEMBER,
                    inject={constants.MEMBER: member}))
            '''
            LOG.info('get_delete:pool is %s', pool.to_dict())
            if pool.health_monitor is not None:
                    dict_health_monitor = pool.health_monitor.to_dict()
                    dict_health_monitor[constants.HEALTHMONITOR_ID] = pool.health_monitor.id
                    LOG.info('delete health_monitor %s', pool.health_monitor.id)
                    delete_pools_member_health_flow.add(fortiadc_driver_tasks.HealthMonitorDeleteObj(
                        requires=constants.HEALTH_MON,
                        inject={constants.HEALTH_MON: pool.health_monitor}))
        LOG.info('end to remove member and health_monitor')

        return delete_pools_member_health_flow
