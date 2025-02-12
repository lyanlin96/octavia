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


class ListenerFlows(object):

    def get_create_listener_flow(self):
        create_listener_flow = linear_flow.Flow(constants.CREATE_LISTENER_FLOW)
        create_listener_flow.add(fadc_lifecycle_tasks.ListenersToErrorOnRevertTask(
            requires=constants.LISTENERS))

        create_listener_flow.add(fortiadc_driver_tasks.ListenerCreate(
            requires=constants.LISTENERS
        ))

        create_listener_flow.add(fadc_database_tasks.
                                 MarkLBAndListenersActiveInDB(
                                     requires=(constants.LOADBALANCER_ID,
                                               constants.LISTENERS)))
        return create_listener_flow

    def get_create_all_listeners_flow(self):
        create_all_listeners_flow = linear_flow.Flow(
            constants.CREATE_LISTENERS_FLOW)
        create_all_listeners_flow.add(
            fadc_database_tasks.GetListenersFromLoadbalancer(
                requires=constants.LOADBALANCER,
                provides=constants.LISTENERS))
        create_all_listeners_flow.add(fadc_database_tasks.ReloadLoadBalancer(
            requires=constants.LOADBALANCER_ID,
            provides=constants.LOADBALANCER))
        return create_all_listeners_flow

    def get_delete_listener_flow(self):
        delete_listener_flow = linear_flow.Flow(constants.DELETE_LISTENER_FLOW)
        delete_listener_flow.add(fadc_lifecycle_tasks.ListenerToErrorOnRevertTask(
            requires=constants.LISTENER))
        delete_listener_flow.add(fortiadc_driver_tasks.ListenerDelete(
            requires=constants.LISTENER))
        delete_listener_flow.add(fadc_database_tasks.DeleteListenerInDB(
            requires=constants.LISTENER))
        delete_listener_flow.add(fadc_database_tasks.DecrementListenerQuota(
            requires=constants.PROJECT_ID))
        delete_listener_flow.add(fadc_database_tasks.MarkLBActiveInDBByListener(
            requires=constants.LISTENER))

        return delete_listener_flow

    def get_delete_listener_internal_flow(self, listener):
        listener_id = listener[constants.LISTENER_ID]
        delete_listener_flow = linear_flow.Flow(
            constants.DELETE_LISTENER_FLOW + '-' + listener_id)
        delete_listener_flow.add(fortiadc_driver_tasks.ListenerDelete(
            name='delete_listener_in_adc_' + listener_id,
            requires=constants.LISTENER,
            inject={constants.LISTENER: listener}))

        delete_listener_flow.add(fadc_database_tasks.DeleteListenerInDB(
            name='delete_listener_in_db_' + listener_id,
            requires=constants.LISTENER,
            inject={constants.LISTENER: listener}))
        delete_listener_flow.add(fadc_database_tasks.DecrementListenerQuota(
            name='decrement_listener_quota_' + listener_id,
            requires=constants.PROJECT_ID))

        return delete_listener_flow

    def get_update_listener_flow(self):
        update_listener_flow = linear_flow.Flow(constants.UPDATE_LISTENER_FLOW)
        update_listener_flow.add(fadc_lifecycle_tasks.ListenerToErrorOnRevertTask(
            requires=constants.LISTENER))
        update_listener_flow.add(fortiadc_driver_tasks.ListenersUpdate(
            requires=constants.LOADBALANCER_ID))
        update_listener_flow.add(fadc_database_tasks.UpdateListenerInDB(
            requires=[constants.LISTENER, constants.UPDATE_DICT]))
        update_listener_flow.add(fadc_database_tasks.
                                 MarkLBAndListenersActiveInDB(
                                     requires=(constants.LOADBALANCER_ID,
                                               constants.LISTENERS)))

        return update_listener_flow
