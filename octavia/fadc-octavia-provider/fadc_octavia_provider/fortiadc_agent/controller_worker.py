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

from octavia_lib.common import constants as lib_consts
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from sqlalchemy.orm import exc as db_exceptions
from stevedore import driver as stevedore_driver
from taskflow.listeners import logging as tf_logging
import tenacity

from octavia.amphorae.driver_exceptions import exceptions as driver_exc
from octavia.api.drivers import utils as provider_utils
from octavia.common import base_taskflow
from octavia.common import constants
from octavia.common import exceptions
from octavia.common import utils
from fadc_octavia_provider.fortiadc_agent.flows import flow_utils
#from octavia.controller.worker.v2 import taskflow_jobboard_driver as tsk_driver
from octavia.db import api as db_apis
from octavia.db import repositories as repo
from octavia_lib.api.drivers import driver_lib
from fadc_octavia_provider.fortiadc_agent.fadc_device_driver import FadcdeviceDriver

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def retryMaskFilter(record):
    if record.exc_info is not None and isinstance(
            record.exc_info[1], (
                driver_exc.AmpConnectionRetry,
                exceptions.ComputeWaitTimeoutException)):
        return False
    return True


LOG.logger.addFilter(retryMaskFilter)


def _is_provisioning_status_pending_update(lb_obj):
    return not lb_obj.provisioning_status == constants.PENDING_UPDATE


class ControllerWorker(object):

    def __init__(self):

        self._health_mon_repo = repo.HealthMonitorRepository()
        self._lb_repo = repo.LoadBalancerRepository()
        self._listener_repo = repo.ListenerRepository()
        self._member_repo = repo.MemberRepository()
        self._pool_repo = repo.PoolRepository()

        self.driver_lib = driver_lib.DriverLibrary(
            status_socket=CONF.driver_agent.status_socket_path,
            stats_socket=CONF.driver_agent.stats_socket_path,
            get_socket=CONF.driver_agent.get_socket_path,
        )

        if CONF.task_flow.jobboard_enabled:
            persistence = tsk_driver.MysqlPersistenceDriver()

            self.jobboard_driver = stevedore_driver.DriverManager(
                namespace='octavia.worker.jobboard_driver',
                name=CONF.task_flow.jobboard_backend_driver,
                invoke_args=(persistence,),
                invoke_on_load=True).driver
        else:
            self.tf_engine = base_taskflow.BaseTaskFlowEngine()

    @tenacity.retry(
        retry=(
            tenacity.retry_if_result(_is_provisioning_status_pending_update) |
            tenacity.retry_if_exception_type()),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def _get_db_obj_until_pending_update(self, repo, id):

        return repo.get(db_apis.get_session(), id=id)

    @property
    def services_controller(self):
        return base_taskflow.TaskFlowServiceController(self.jobboard_driver)

    def run_flow(self, func, *args, **kwargs):
        if CONF.task_flow.jobboard_enabled:
            self.services_controller.run_poster(func, *args, **kwargs)
        else:
            store = kwargs.pop('store', None)
            tf = self.tf_engine.taskflow_load(
                func(*args, **kwargs), store=store)
            with tf_logging.DynamicLoggingListener(tf, log=LOG):
                tf.run()

    def delete_amphora(self, amphora_id):
        try:
            amphora = self._amphora_repo.get(db_apis.get_session(),
                                             id=amphora_id)
            store = {constants.AMPHORA: amphora.to_dict()}
            self.run_flow(
                flow_utils.get_delete_amphora_flow,
                store=store)
        except Exception as e:
            LOG.error('Failed to delete a amphora %s due to: %s',
                      amphora_id, str(e))
            return
        LOG.info('Finished deleting amphora %s.', amphora_id)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(db_exceptions.NoResultFound),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def create_health_monitor(self, health_monitor):
        """Creates a health monitor.

        :param health_monitor: Provider health monitor dict
        :returns: None
        :raises NoResultFound: Unable to find the object
        """
        LOG.info('create_health_monitor %s', health_monitor)
        db_health_monitor = self._health_mon_repo.get(
            db_apis.get_session(),
            id=health_monitor[constants.HEALTHMONITOR_ID])

        if not db_health_monitor:
            LOG.warning('Failed to fetch %s %s from DB. Retrying for up to '
                        '60 seconds.', 'healthmonitor',
                        health_monitor[constants.HEALTHMONITOR_ID])
            raise db_exceptions.NoResultFound

        pool = db_health_monitor.pool
        pool.health_monitor = db_health_monitor
        load_balancer = pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {constants.HEALTH_MON: health_monitor,
                 constants.POOL_ID: pool.id,
                 constants.LISTENERS: listeners_dicts,
                 constants.LOADBALANCER_ID: load_balancer.id,
                 constants.LOADBALANCER: provider_lb}
        self.run_flow(
            flow_utils.get_create_health_monitor_flow,
            store=store)

    def delete_health_monitor(self, health_monitor):
        """Deletes a health monitor.

        :param health_monitor: Provider health monitor dict
        :returns: None
        :raises HMNotFound: The referenced health monitor was not found
        """
        db_health_monitor = self._health_mon_repo.get(
            db_apis.get_session(),
            id=health_monitor[constants.HEALTHMONITOR_ID])

        pool = db_health_monitor.pool
        load_balancer = pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {constants.HEALTH_MON: health_monitor,
                 constants.POOL_ID: pool.id,
                 constants.LISTENERS: listeners_dicts,
                 constants.LOADBALANCER_ID: load_balancer.id,
                 constants.LOADBALANCER: provider_lb,
                 constants.PROJECT_ID: load_balancer.project_id}
        self.run_flow(
            flow_utils.get_delete_health_monitor_flow,
            store=store)

    def update_health_monitor(self, original_health_monitor,
                              health_monitor_updates):
        """Updates a health monitor.

        :param original_health_monitor: Provider health monitor dict
        :param health_monitor_updates: Dict containing updated health monitor
        :returns: None
        :raises HMNotFound: The referenced health monitor was not found
        """
        try:
            db_health_monitor = self._get_db_obj_until_pending_update(
                self._health_mon_repo,
                original_health_monitor[constants.HEALTHMONITOR_ID])
        except tenacity.RetryError as e:
            LOG.warning('Health monitor did not go into %s in 60 seconds. '
                        'This either due to an in-progress Octavia upgrade '
                        'or an overloaded and failing database. Assuming '
                        'an upgrade is in progress and continuing.',
                        constants.PENDING_UPDATE)
            db_health_monitor = e.last_attempt.result()

        pool = db_health_monitor.pool

        load_balancer = pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {constants.HEALTH_MON: original_health_monitor,
                 constants.POOL_ID: pool.id,
                 constants.LISTENERS: listeners_dicts,
                 constants.LOADBALANCER_ID: load_balancer.id,
                 constants.LOADBALANCER: provider_lb,
                 constants.UPDATE_DICT: health_monitor_updates}
        self.run_flow(
            flow_utils.get_update_health_monitor_flow,
            store=store)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(db_exceptions.NoResultFound),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def create_listener(self, listener):
        """Creates a listener.

        :param listener: A listener provider dictionary.
        :returns: None
        :raises NoResultFound: Unable to find the object
        """
        LOG.info('create_listener: listener %s', listener)
        db_listener = self._listener_repo.get(
            db_apis.get_session(), id=listener[constants.LISTENER_ID])
        if not db_listener:
            LOG.warning('Failed to fetch %s %s from DB. Retrying for up to '
                        '60 seconds.', 'listener',
                        listener[constants.LISTENER_ID])
            raise db_exceptions.NoResultFound

        load_balancer = db_listener.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)

        store = {constants.LISTENERS: provider_lb['listeners'],
        #store = {constants.LISTENERS: db_listener,
                 constants.LOADBALANCER: provider_lb,
                 constants.LOADBALANCER_ID: load_balancer.id}

        LOG.info('create_listener: store is %s', store)
        self.run_flow(
            flow_utils.get_create_listener_flow,
            store=store)

    def delete_listener(self, listener):
        """Deletes a listener.

        :param listener: A listener provider dictionary to delete
        :returns: None
        :raises ListenerNotFound: The referenced listener was not found
        """
        store = {constants.LISTENER: listener,
                 constants.LOADBALANCER_ID:
                     listener[constants.LOADBALANCER_ID],
                 constants.PROJECT_ID: listener[constants.PROJECT_ID]}
        self.run_flow(
            flow_utils.get_delete_listener_flow,
            store=store)

    def update_listener(self, listener, listener_updates):
        """Updates a listener.

        :param listener: A listener provider dictionary to update
        :param listener_updates: Dict containing updated listener attributes
        :returns: None
        :raises ListenerNotFound: The referenced listener was not found
        """
        try:
            db_lb = self._get_db_obj_until_pending_update(
                self._lb_repo, listener[constants.LOADBALANCER_ID])
        except tenacity.RetryError as e:
            LOG.warning('Loadbalancer did not go into %s in 60 seconds. '
                        'This either due to an in-progress Octavia upgrade '
                        'or an overloaded and failing database. Assuming '
                        'an upgrade is in progress and continuing.',
                        constants.PENDING_UPDATE)
            db_lb = e.last_attempt.result()

        store = {constants.LISTENER: listener,
                 constants.UPDATE_DICT: listener_updates,
                 constants.LOADBALANCER_ID: db_lb.id,
                 constants.LISTENERS: [listener]}
        self.run_flow(
            flow_utils.get_update_listener_flow,
            store=store)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(db_exceptions.NoResultFound),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def create_load_balancer(self, loadbalancer, flavor=None,
                             availability_zone=None):
        """Creates a load balancer by allocating Amphorae.

        First tries to allocate an existing Amphora in READY state.
        If none are available it will attempt to build one specifically
        for this load balancer.

        :param loadbalancer: The dict of load balancer to create
        :returns: None
        :raises NoResultFound: Unable to find the object
        """
        LOG.info('load_balancer create, loadbalancer %s', loadbalancer)
        lb = self._lb_repo.get(db_apis.get_session(),
                               id=loadbalancer[constants.LOADBALANCER_ID])
        if not lb:
            LOG.warning('Failed to fetch %s %s from DB. Retrying for up to '
                        '60 seconds.', 'load_balancer',
                        loadbalancer[constants.LOADBALANCER_ID])
            raise db_exceptions.NoResultFound

        store = {lib_consts.LOADBALANCER_ID:
                 loadbalancer[lib_consts.LOADBALANCER_ID],
                 constants.BUILD_TYPE_PRIORITY:
                 constants.LB_CREATE_NORMAL_PRIORITY,
                 lib_consts.FLAVOR: flavor,
                 lib_consts.AVAILABILITY_ZONE: availability_zone}

        topology = lb.topology
        if (not CONF.nova.enable_anti_affinity or
                topology == constants.TOPOLOGY_SINGLE):
            store[constants.SERVER_GROUP_ID] = None

        listeners_dicts = (
            provider_utils.db_listeners_to_provider_dicts_list_of_dicts(
                lb.listeners)
        )

        store[constants.UPDATE_DICT] = {
            constants.TOPOLOGY: topology
        }
        LOG.info('load_balancer create, listeners_dicts %s', listeners_dicts)
        LOG.info(listeners_dicts)
        self.run_flow(
            flow_utils.get_create_load_balancer_flow,
            topology, listeners=listeners_dicts,
            store=store)

    def delete_load_balancer(self, load_balancer, cascade=False):
        """Deletes a load balancer by de-allocating Amphorae.

        :param load_balancer: Dict of the load balancer to delete
        :returns: None
        :raises LBNotFound: The referenced load balancer was not found
        """
        loadbalancer_id = load_balancer[constants.LOADBALANCER_ID]
        db_lb = self._lb_repo.get(db_apis.get_session(), id=loadbalancer_id)
        store = {constants.LOADBALANCER: load_balancer,
                 constants.LOADBALANCER_ID: loadbalancer_id,
                 constants.SERVER_GROUP_ID: db_lb.server_group_id,
                 constants.PROJECT_ID: db_lb.project_id}
        if cascade:
            listeners = flow_utils.get_listeners_on_lb(db_lb)
            pools = flow_utils.get_pools_on_lb(db_lb)

            self.run_flow(
                flow_utils.get_cascade_delete_load_balancer_flow,
                load_balancer, listeners, pools, store=store)

            self.run_flow(
                flow_utils.get_delete_pools_member_health_flow, db_lb.pools)

            '''
            LOG.info('start to remove member and health_monitor')
            for pool in db_lb.pools:
                for member in pool.members:
                    dict_member = member.to_dict()
                    dict_member[constants.MEMBER_ID] = member.id
                    self.delete_member(dict_member)

                if pool.health_monitor:
                    dict_health_monitor = pool.health_monitor.to_dict()
                    dict_health_monitor[constants.HEALTHMONITOR_ID] = pool.health_monitor.id
                    LOG.info('deploy health_monitor %s', pool.health_monitor.id)
                    self.delete_health_monitor(dict_health_monitor)
            LOG.info('End to remove member and health_monitor')
            '''
        else:
            self.run_flow(
                flow_utils.get_delete_load_balancer_flow,
                load_balancer, store=store)

    def update_load_balancer(self, original_load_balancer,
                             load_balancer_updates):
        """Updates a load balancer.

        :param original_load_balancer: Dict of the load balancer to update
        :param load_balancer_updates: Dict containing updated load balancer
        :returns: None
        :raises LBNotFound: The referenced load balancer was not found
        """

        try:
            self._get_db_obj_until_pending_update(
                self._lb_repo,
                original_load_balancer[constants.LOADBALANCER_ID])
        except tenacity.RetryError:
            LOG.warning('Load balancer did not go into %s in 60 seconds. '
                        'This either due to an in-progress Octavia upgrade '
                        'or an overloaded and failing database. Assuming '
                        'an upgrade is in progress and continuing.',
                        constants.PENDING_UPDATE)

        store = {constants.LOADBALANCER: original_load_balancer,
                 constants.LOADBALANCER_ID:
                     original_load_balancer[constants.LOADBALANCER_ID],
                 constants.UPDATE_DICT: load_balancer_updates}

        self.run_flow(
            flow_utils.get_update_load_balancer_flow,
            store=store)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(db_exceptions.NoResultFound),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def create_member(self, member):
        """Creates a pool member.

        :param member: A member provider dictionary to create
        :returns: None
        :raises NoSuitablePool: Unable to find the node pool
        """
        LOG.info('create_member:member %s', member)
        db_member = self._member_repo.get(db_apis.get_session(),
                                          id=member[constants.MEMBER_ID])
        if not db_member:
            LOG.warning('Failed to fetch %s %s from DB. Retrying for up to '
                        '60 seconds.', 'l7member',
                        member[constants.MEMBER_ID])
            raise db_exceptions.NoResultFound

        pool = db_member.pool
        load_balancer = pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {
            constants.MEMBER: member,
            constants.LISTENERS: listeners_dicts,
            constants.LOADBALANCER_ID: load_balancer.id,
            constants.LOADBALANCER: provider_lb,
            constants.POOL_ID: pool.id}
        if load_balancer.availability_zone:
            store[constants.AVAILABILITY_ZONE] = (
                self._az_repo.get_availability_zone_metadata_dict(
                    db_apis.get_session(), load_balancer.availability_zone))
        else:
            store[constants.AVAILABILITY_ZONE] = {}

        self.run_flow(
            flow_utils.get_create_member_flow,
            store=store)

    def delete_member(self, member):
        """Deletes a pool member.

        :param member: A member provider dictionary to delete
        :returns: None
        :raises MemberNotFound: The referenced member was not found
        """
        pool = self._pool_repo.get(db_apis.get_session(),
                                   id=member[constants.POOL_ID])

        load_balancer = pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {
            constants.MEMBER: member,
            constants.LISTENERS: listeners_dicts,
            constants.LOADBALANCER_ID: load_balancer.id,
            constants.LOADBALANCER: provider_lb,
            constants.POOL_ID: pool.id,
            constants.PROJECT_ID: load_balancer.project_id}
        if load_balancer.availability_zone:
            store[constants.AVAILABILITY_ZONE] = (
                self._az_repo.get_availability_zone_metadata_dict(
                    db_apis.get_session(), load_balancer.availability_zone))
        else:
            store[constants.AVAILABILITY_ZONE] = {}

        self.run_flow(
            flow_utils.get_delete_member_flow,
            store=store)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(db_exceptions.NoResultFound),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def batch_update_members(self, old_members, new_members,
                             updated_members):
        db_new_members = [self._member_repo.get(db_apis.get_session(),
                                                id=member[constants.MEMBER_ID])
                          for member in new_members]
        # The API may not have commited all of the new member records yet.
        # Make sure we retry looking them up.
        if None in db_new_members or len(db_new_members) != len(new_members):
            LOG.warning('Failed to fetch one of the new members from DB. '
                        'Retrying for up to 60 seconds.')
            raise db_exceptions.NoResultFound

        updated_members = [
            (provider_utils.db_member_to_provider_member(
                self._member_repo.get(db_apis.get_session(),
                                      id=m.get(constants.ID))).to_dict(),
             m)
            for m in updated_members]
        provider_old_members = [
            provider_utils.db_member_to_provider_member(
                self._member_repo.get(db_apis.get_session(),
                                      id=m.get(constants.ID))).to_dict()
            for m in old_members]
        if old_members:
            pool = self._pool_repo.get(db_apis.get_session(),
                                       id=old_members[0][constants.POOL_ID])
        elif new_members:
            pool = self._pool_repo.get(db_apis.get_session(),
                                       id=new_members[0][constants.POOL_ID])
        else:
            pool = self._pool_repo.get(
                db_apis.get_session(),
                id=updated_members[0][0][constants.POOL_ID])
        load_balancer = pool.load_balancer

        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {
            constants.LISTENERS: listeners_dicts,
            constants.LOADBALANCER_ID: load_balancer.id,
            constants.LOADBALANCER: provider_lb,
            constants.POOL_ID: pool.id,
            constants.PROJECT_ID: load_balancer.project_id}
        if load_balancer.availability_zone:
            store[constants.AVAILABILITY_ZONE] = (
                self._az_repo.get_availability_zone_metadata_dict(
                    db_apis.get_session(), load_balancer.availability_zone))
        else:
            store[constants.AVAILABILITY_ZONE] = {}

        self.run_flow(
            flow_utils.get_batch_update_members_flow,
            provider_old_members, new_members, updated_members,
            store=store)

    def update_member(self, member, member_updates):
        """Updates a pool member.

        :param member_id: A member provider dictionary  to update
        :param member_updates: Dict containing updated member attributes
        :returns: None
        :raises MemberNotFound: The referenced member was not found
        """

        try:
            db_member = self._get_db_obj_until_pending_update(
                self._member_repo, member[constants.MEMBER_ID])
        except tenacity.RetryError as e:
            LOG.warning('Member did not go into %s in 60 seconds. '
                        'This either due to an in-progress Octavia upgrade '
                        'or an overloaded and failing database. Assuming '
                        'an upgrade is in progress and continuing.',
                        constants.PENDING_UPDATE)
            db_member = e.last_attempt.result()

        pool = db_member.pool
        load_balancer = pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])
        store = {
            constants.MEMBER: member,
            constants.LISTENERS: listeners_dicts,
            constants.LOADBALANCER_ID: load_balancer.id,
            constants.LOADBALANCER: provider_lb,
            constants.POOL_ID: pool.id,
            constants.UPDATE_DICT: member_updates}
        if load_balancer.availability_zone:
            store[constants.AVAILABILITY_ZONE] = (
                self._az_repo.get_availability_zone_metadata_dict(
                    db_apis.get_session(), load_balancer.availability_zone))
        else:
            store[constants.AVAILABILITY_ZONE] = {}

        self.run_flow(
            flow_utils.get_update_member_flow,
            store=store)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(db_exceptions.NoResultFound),
        wait=tenacity.wait_incrementing(
            CONF.haproxy_amphora.api_db_commit_retry_initial_delay,
            CONF.haproxy_amphora.api_db_commit_retry_backoff,
            CONF.haproxy_amphora.api_db_commit_retry_max),
        stop=tenacity.stop_after_attempt(
            CONF.haproxy_amphora.api_db_commit_retry_attempts))
    def create_pool(self, pool):
        """Creates a node pool.

        :param pool: Provider pool dict to create
        :returns: None
        :raises NoResultFound: Unable to find the object
        """

        # TODO(ataraday) It seems we need to get db pool here anyway to get
        # proper listeners
        LOG.info('create_pool: pool %s', pool)
        db_pool = self._pool_repo.get(db_apis.get_session(),
                                      id=pool[constants.POOL_ID])
        if not db_pool:
            LOG.warning('Failed to fetch %s %s from DB. Retrying for up to '
                        '60 seconds.', 'pool', pool[constants.POOL_ID])
            raise db_exceptions.NoResultFound

        load_balancer = db_pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {constants.POOL_ID: pool[constants.POOL_ID],
                 constants.LISTENERS: listeners_dicts,
                 constants.LOADBALANCER_ID: load_balancer.id,
                 constants.LOADBALANCER: provider_lb}
        self.run_flow(
            flow_utils.get_create_pool_flow,
            store=store)

    def delete_pool(self, pool):
        """Deletes a node pool.

        :param pool: Provider pool dict to delete
        :returns: None
        :raises PoolNotFound: The referenced pool was not found
        """
        db_pool = self._pool_repo.get(db_apis.get_session(),
                                      id=pool[constants.POOL_ID])

        load_balancer = db_pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {constants.POOL_ID: pool[constants.POOL_ID],
                 constants.LISTENERS: listeners_dicts,
                 constants.LOADBALANCER: provider_lb,
                 constants.LOADBALANCER_ID: load_balancer.id,
                 constants.PROJECT_ID: db_pool.project_id}
        self.run_flow(
            flow_utils.get_delete_pool_flow,
            store=store)

    def update_pool(self, origin_pool, pool_updates):
        """Updates a node pool.

        :param origin_pool: Provider pool dict to update
        :param pool_updates: Dict containing updated pool attributes
        :returns: None
        :raises PoolNotFound: The referenced pool was not found
        """
        try:
            db_pool = self._get_db_obj_until_pending_update(
                self._pool_repo, origin_pool[constants.POOL_ID])
        except tenacity.RetryError as e:
            LOG.warning('Pool did not go into %s in 60 seconds. '
                        'This either due to an in-progress Octavia upgrade '
                        'or an overloaded and failing database. Assuming '
                        'an upgrade is in progress and continuing.',
                        constants.PENDING_UPDATE)
            db_pool = e.last_attempt.result()

        load_balancer = db_pool.load_balancer
        provider_lb = provider_utils.db_loadbalancer_to_provider_loadbalancer(
            load_balancer).to_dict(recurse=True)
        listeners_dicts = provider_lb.get('listeners', [])

        store = {constants.POOL_ID: db_pool.id,
                 constants.LISTENERS: listeners_dicts,
                 constants.LOADBALANCER: provider_lb,
                 constants.LOADBALANCER_ID: load_balancer.id,
                 constants.UPDATE_DICT: pool_updates}
        self.run_flow(
            flow_utils.get_update_pool_flow,
            store=store)

    def deploy_loadbalancer(self, lb):
        dict_lb = lb.to_dict()
        dict_lb[constants.LOADBALANCER_ID] = lb.id
        LOG.info('deploy loadbalncer ')
        self.create_load_balancer(dict_lb)
        LOG.info('deploy loadbalncer end')
        if lb.pools:
            for pool in lb.pools:
                dict_pool = pool.to_dict()
                dict_pool[constants.POOL_ID] = pool.id
                LOG.info('deploy pool %s', pool.id)
                self.create_pool(dict_pool)
                for member in pool.members:
                    dict_member = member.to_dict()
                    dict_member[constants.MEMBER_ID] = member.id
                    LOG.info('deploy member %s', member.id)
                    self.create_member(dict_member)

                if pool.health_monitor:
                    dict_health_monitor = pool.health_monitor.to_dict()
                    dict_health_monitor[constants.HEALTHMONITOR_ID] = pool.health_monitor.id
                    LOG.info('deploy health_monitor %s', pool.health_monitor.id)
                    self.create_health_monitor(dict_health_monitor)


    def sync_state(self, name):
        LOG.debug('sync_state called')
        delete_lb_list, _ = self._lb_repo.get_all(db_apis.get_session(), provisioning_status='PENDING_DELETE', provider='fortiadc_driver')
        for lb in delete_lb_list:
            LOG.debug('sync_state: delete lb %s', lb.id)
            dict_lb = lb.to_dict()
            dict_lb[constants.LOADBALANCER_ID] = lb.id
            self.delete_load_balancer(dict_lb, True)

        active_lb_list, _ = self._lb_repo.get_all(db_apis.get_session(), provisioning_status='ACTIVE', provider='fortiadc_driver')
        for lb in active_lb_list:
            LOG.debug('sync_state: check lb %s', lb.id)
            if lb.listeners:
                for listener in lb.listeners:
                    LOG.debug('sync_state: check listener %s', listener.id)
                    res = FadcdeviceDriver(CONF, listener.project_id).listener.get_status(listener)
                    LOG.debug('sync_state: res is %s', res)
                    if res:
                        if isinstance(res, str) and res.find('payload') and len(res) < 20:
                            LOG.debug('sync_state: len is %d', len(res))
                            try:
                                self.deploy_loadbalancer(lb)
                            except:
                                LOG.error('sync_state: failed to deploy %s', listener.id)


    def sync_stats(self, name):
        active_lb_list, _ = self._lb_repo.get_all(db_apis.get_session(), provisioning_status='ACTIVE', provider='fortiadc_driver')
        total_listener_stats = []
        for lb in active_lb_list:
            if lb.listeners:
                res = FadcdeviceDriver(CONF, lb.listeners[0].project_id).listener.get_stats(lb.listeners)
                if res:
                    LOG.debug('sync_state: res is %s', res)
                    if isinstance(res, list):
                        LOG.debug('sync_stats: len is %d', len(res))
                        for stats in res:
                            total_listener_stats.append(stats)

        if len(total_listener_stats) > 0:
            update_stats = {'listeners': total_listener_stats}
            self.driver_lib.update_listener_statistics(update_stats)
