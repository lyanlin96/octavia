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

from jsonschema import exceptions as js_exceptions
from jsonschema import validate
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging

from octavia.common import constants
from octavia.common import rpc
from octavia.db import api as db_apis
from octavia.db import repositories
from octavia.common import constants as consts
from octavia_lib.api.drivers import data_models as driver_dm
from octavia_lib.api.drivers import exceptions
from octavia_lib.api.drivers import provider_base 

CONF = cfg.CONF
CONF.import_group('oslo_messaging', 'octavia.common.config')
LOG = logging.getLogger(__name__)

class FortiadcDriver(provider_base.ProviderDriver):
    def __init__(self):
        super(FortiadcDriver, self).__init__()
        self.target = messaging.Target(
            namespace=constants.RPC_NAMESPACE_CONTROLLER_AGENT,
            topic='fortiadc_octavia_topic', version='2.0', fanout=False
        )
        self.client = rpc.get_client(self.target)
        self.repositories = repositories.Repositories()
        LOG.debug('driver: FortiadcDriver init')

    def create_vip_port(self, loadbalancer_id, project_id, vip_dictionary, additional_vip_dicts):
        raise exceptions.NotImplementedError(
            user_fault_string='Fortiadc provider does not implement custom create_vip_port()',
            operator_fault_string='Fortiadc provider does not implement custom create_vip_port()'
        )

    def loadbalancer_create(self, loadbalancer):
        LOG.debug('driver: loadbalancer_create')
        if loadbalancer.flavor == driver_dm.Unset:
            loadbalancer.flavor = None
        if loadbalancer.availability_zone == driver_dm.Unset:
            loadbalancer.availability_zone = None
        payload = {consts.LOADBALANCER: loadbalancer.to_dict(),
                   consts.FLAVOR: loadbalancer.flavor,
                   consts.AVAILABILITY_ZONE: loadbalancer.availability_zone}
        self.client.cast({}, 'create_load_balancer', **payload)

    def loadbalancer_delete(self, loadbalancer, cascade=False):
        LOG.debug('driver: loadbalancer_delete')
        payload = {consts.LOADBALANCER: loadbalancer.to_dict(),
                   'cascade': cascade}
        self.client.cast({}, 'delete_load_balancer', **payload)

    def loadbalancer_failover(self, loadbalancer_id):
        LOG.debug('driver: loadbalancer_failover')
        payload = {consts.LOAD_BALANCER_ID: loadbalancer_id}
        self.client.cast({}, 'failover_load_balancer', **payload)

    def loadbalancer_update(self, old_loadbalancer, new_loadbalancer):
        LOG.debug('driver: loadbalancer_update')

        lb_dict = new_loadbalancer.to_dict()
        if 'admin_state_up' in lb_dict:
            lb_dict['enabled'] = lb_dict.pop('admin_state_up')
        lb_id = lb_dict.pop('loadbalancer_id')
        vip_qos_policy_id = lb_dict.pop('vip_qos_policy_id', None)
        if vip_qos_policy_id:
            vip_dict = {"qos_policy_id": vip_qos_policy_id}
            lb_dict["vip"] = vip_dict

        payload = {constants.LOAD_BALANCER_ID: lb_id,
                   constants.LOAD_BALANCER_UPDATES: lb_dict}
        self.client.cast({}, 'update_load_balancer', **payload)

    def listener_create(self, listener):
        LOG.debug('driver: listener_create')
        payload = {consts.LISTENER: listener.to_dict()}

        self.client.cast({}, 'create_listener', **payload)

    def listener_delete(self, listener):
        LOG.debug('driver: listener_delete')
        payload = {consts.LISTENER: listener.to_dict()}
        self.client.cast({}, 'delete_listener', **payload)

    def listener_update(self, old_listener, new_listener):
        LOG.debug('driver: listener_update')
        original_listener = old_listener.to_dict()
        listener_updates = new_listener.to_dict()

        payload = {consts.ORIGINAL_LISTENER: original_listener,
                   consts.LISTENER_UPDATES: listener_updates}
        self.client.cast({}, 'update_listener', **payload)


    def _pool_convert_to_dict(self, pool):
        pool_dict = pool.to_dict(recurse=True)
        if 'admin_state_up' in pool_dict:
            pool_dict['enabled'] = pool_dict.pop('admin_state_up')
        if 'tls_container_ref' in pool_dict:
            pool_dict['tls_certificate_id'] = pool_dict.pop(
                'tls_container_ref')
        pool_dict.pop('tls_container_data', None)
        if 'ca_tls_container_ref' in pool_dict:
            pool_dict['ca_tls_certificate_id'] = pool_dict.pop(
                'ca_tls_container_ref')
        pool_dict.pop('ca_tls_container_data', None)
        if 'crl_container_ref' in pool_dict:
            pool_dict['crl_container_id'] = pool_dict.pop('crl_container_ref')
        pool_dict.pop('crl_container_data', None)
        return pool_dict

    def pool_create(self, pool):
        LOG.debug('driver: pool_create')
        payload = {consts.POOL: self._pool_convert_to_dict(pool)}
        self.client.cast({}, 'create_pool', **payload)

    def pool_delete(self, pool):
        LOG.debug('driver: pool_delete')
        payload = {consts.POOL: pool.to_dict(recurse=True)}
        self.client.cast({}, 'delete_pool', **payload)

    def pool_update(self, old_pool, new_pool):
        LOG.debug('driver: pool_update')
        pool_dict = self._pool_convert_to_dict(new_pool)
        pool_dict.pop('pool_id')
        payload = {consts.ORIGINAL_POOL: old_pool.to_dict(),
                   consts.POOL_UPDATES: pool_dict}
        self.client.cast({}, 'update_pool', **payload)

    def member_create(self, member):
        LOG.debug('driver: member_create')
        pool_id = member.pool_id
        db_pool = self.repositories.pool.get(db_apis.get_session(),
                                             id=pool_id)
        payload = {consts.MEMBER: member.to_dict()}
        self.client.cast({}, 'create_member', **payload)

    def member_delete(self, member):
        LOG.debug('driver: member_delete')
        payload = {consts.MEMBER: member.to_dict()}
        self.client.cast({}, 'delete_member', **payload)

    def member_update(self, old_member, new_member):
        LOG.debug('driver: member_update')
        original_member = old_member.to_dict()
        member_updates = new_member.to_dict()
        if 'admin_state_up' in member_updates:
            member_updates['enabled'] = member_updates.pop('admin_state_up')
        member_updates.pop(consts.MEMBER_ID)
        payload = {consts.ORIGINAL_MEMBER: original_member,
                   consts.MEMBER_UPDATES: member_updates}
        self.client.cast({}, 'update_member', **payload)

    def member_batch_update(self, pool_id, members):
        LOG.debug('driver: member_batch_update')
        db_pool = self.repositories.pool.get(db_apis.get_session(), id=pool_id)

        self._validate_members(db_pool, members)

        old_members = db_pool.members

        old_member_ids = [m.id for m in old_members]
        new_member_ids = [m.member_id for m in members]

        new_members = []
        updated_members = []
        for m in members:
            if m.member_id not in old_member_ids:
                new_members.append(m)
            else:
                member_dict = m.to_dict(render_unsets=False)
                member_dict['id'] = member_dict.pop('member_id')
                if 'address' in member_dict:
                    member_dict['ip_address'] = member_dict.pop('address')
                if 'admin_state_up' in member_dict:
                    member_dict['enabled'] = member_dict.pop('admin_state_up')
                updated_members.append(member_dict)

        deleted_members = []
        for m in old_members:
            if m.id not in new_member_ids:
                deleted_members.append(m)

        payload = {'old_members': [m.to_dict() for m in deleted_members],
                   'new_members': [m.to_dict() for m in new_members],
                   'updated_members': updated_members}
        self.client.cast({}, 'batch_update_members', **payload)

    def health_monitor_create(self, healthmonitor):
        LOG.debug('driver: health_monitor_create')
        payload = {consts.HEALTH_MONITOR: healthmonitor.to_dict()}
        self.client.cast({}, 'create_health_monitor', **payload)

    def health_monitor_delete(self, healthmonitor):
        LOG.debug('driver: health_monitor_delete')
        payload = {consts.HEALTH_MONITOR: healthmonitor.to_dict()}
        self.client.cast({}, 'delete_health_monitor', **payload)

    def health_monitor_update(self, old_healthmonitor, new_healthmonitor):
        LOG.debug('driver: health_monitor_update')
        healthmon_dict = new_healthmonitor.to_dict()
        if 'admin_state_up' in healthmon_dict:
            healthmon_dict['enabled'] = healthmon_dict.pop('admin_state_up')
        if 'max_retries_down' in healthmon_dict:
            healthmon_dict['fall_threshold'] = healthmon_dict.pop(
                'max_retries_down')
        if 'max_retries' in healthmon_dict:
            healthmon_dict['rise_threshold'] = healthmon_dict.pop(
                'max_retries')
        healthmon_dict.pop('healthmonitor_id')

        payload = {consts.ORIGINAL_HEALTH_MONITOR: old_healthmonitor.to_dict(),
                   consts.HEALTH_MONITOR_UPDATES: healthmon_dict}
        self.client.cast({}, 'update_health_monitor', **payload)


    def l7policy_create(self, l7policy):
        LOG.info('l7policy create is not supported')

    def l7policy_delete(self, l7policy):
        LOG.info('l7policy delete is not supported')

    def l7policy_update(self, old_l7policy, new_l7policy):
        LOG.info('l7policy update is not supported')

    def l7rule_delete(self, l7rule):
        LOG.info('l7rule delete is not supported')

    def l7rule_update(self, old_l7rule, new_l7rule):
        LOG.info('l7rule update is not supported')
