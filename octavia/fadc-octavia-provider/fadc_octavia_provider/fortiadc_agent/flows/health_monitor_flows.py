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

from taskflow.patterns import linear_flow

from octavia.common import constants
from octavia.controller.worker.v2.tasks import database_tasks as fadc_database_tasks
from octavia.controller.worker.v2.tasks import lifecycle_tasks as fadc_lifecycle_tasks
from fadc_octavia_provider.fortiadc_agent.tasks import fortiadc_driver_tasks


class HealthMonitorFlows(object):

    def get_create_health_monitor_flow(self):
        create_hm_flow = linear_flow.Flow(constants.CREATE_HEALTH_MONITOR_FLOW)
        create_hm_flow.add(fadc_lifecycle_tasks.HealthMonitorToErrorOnRevertTask(
            requires=[constants.HEALTH_MON,
                      constants.LISTENERS,
                      constants.LOADBALANCER]))
        create_hm_flow.add(fadc_database_tasks.MarkHealthMonitorPendingCreateInDB(
            requires=constants.HEALTH_MON))
        create_hm_flow.add(fortiadc_driver_tasks.HealthMonitorCreate(
            requires=[constants.HEALTH_MON,
                      constants.LOADBALANCER]
        ))
        create_hm_flow.add(fadc_database_tasks.MarkHealthMonitorActiveInDB(
            requires=constants.HEALTH_MON))
        create_hm_flow.add(fadc_database_tasks.MarkPoolActiveInDB(
            requires=constants.POOL_ID))
        create_hm_flow.add(fadc_database_tasks.MarkLBAndListenersActiveInDB(
            requires=(constants.LOADBALANCER_ID, constants.LISTENERS)))

        return create_hm_flow

    def get_delete_health_monitor_flow(self):
        delete_hm_flow = linear_flow.Flow(constants.DELETE_HEALTH_MONITOR_FLOW)
        delete_hm_flow.add(fadc_lifecycle_tasks.HealthMonitorToErrorOnRevertTask(
            requires=[constants.HEALTH_MON,
                      constants.LISTENERS,
                      constants.LOADBALANCER]))
        delete_hm_flow.add(fadc_database_tasks.MarkHealthMonitorPendingDeleteInDB(
            requires=constants.HEALTH_MON))
        delete_hm_flow.add(fortiadc_driver_tasks.HealthMonitorDelete(
            requires=constants.HEALTH_MON))
        delete_hm_flow.add(fadc_database_tasks.DeleteHealthMonitorInDB(
            requires=constants.HEALTH_MON))
        delete_hm_flow.add(fadc_database_tasks.DecrementHealthMonitorQuota(
            requires=constants.PROJECT_ID))
        delete_hm_flow.add(
            fadc_database_tasks.UpdatePoolMembersOperatingStatusInDB(
                requires=constants.POOL_ID,
                inject={constants.OPERATING_STATUS: constants.NO_MONITOR}))
        delete_hm_flow.add(fadc_database_tasks.MarkPoolActiveInDB(
            requires=constants.POOL_ID))
        delete_hm_flow.add(fadc_database_tasks.MarkLBAndListenersActiveInDB(
            requires=(constants.LOADBALANCER_ID, constants.LISTENERS)))

        return delete_hm_flow

    def get_update_health_monitor_flow(self):
        update_hm_flow = linear_flow.Flow(constants.UPDATE_HEALTH_MONITOR_FLOW)
        update_hm_flow.add(fadc_lifecycle_tasks.HealthMonitorToErrorOnRevertTask(
            requires=[constants.HEALTH_MON,
                      constants.LISTENERS,
                      constants.LOADBALANCER]))
        update_hm_flow.add(fadc_database_tasks.MarkHealthMonitorPendingUpdateInDB(
            requires=constants.HEALTH_MON))
        update_hm_flow.add(fortiadc_driver_tasks.HealthMonitorUpdate(
            requires=[constants.HEALTH_MON,
                      constants.LOADBALANCER]))
        update_hm_flow.add(fadc_database_tasks.UpdateHealthMonInDB(
            requires=[constants.HEALTH_MON, constants.UPDATE_DICT]))
        update_hm_flow.add(fadc_database_tasks.MarkHealthMonitorActiveInDB(
            requires=constants.HEALTH_MON))
        update_hm_flow.add(fadc_database_tasks.MarkPoolActiveInDB(
            requires=constants.POOL_ID))
        update_hm_flow.add(fadc_database_tasks.MarkLBAndListenersActiveInDB(
            requires=(constants.LOADBALANCER_ID, constants.LISTENERS)))

        return update_hm_flow
