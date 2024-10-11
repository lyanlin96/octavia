
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

from fortinet_neutron_lbaas.driver_v2 import FortinetLoadBalancerV2

from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from neutron_lbaas.drivers import driver_base

VERSION = "0.9.0"
LOG = logging.getLogger(__name__)
DRIVER_NAME = "FadcdeviceDriver"

class PearlMilkTeaDriver(driver_base.LoadBalancerBaseDriver):

    def __init__(self, plugin, env='Project'):
        super(PearlMilkTeaDriver, self).__init__(plugin)
        self.device_driver = DRIVER_NAME
       # self.req = OctaviaRequest(cfg.CONF.octavia.base_url,
       #                           keystone.get_session())

        self.load_balancer = LoadBalancerManager(self)
        self.listener = ListenerManager(self)
        self.pool = PoolManager(self)
        self.member = MemberManager(self)
        self.health_monitor = HealthMonitorManager(self)
        LOG.debug("PearlMilkTeaDriver: initialized, version=%s", VERSION)

        self.fortinet = FortinetLoadBalancerV2(plugin, env)

    def start_rpc_listeners(self):
        # call start_rpc_listeners after core_plugin add this driver to create RpcWorker.
        LOG.debug('PearlMilkTeaDriver start_rpc_listeners')
        self.fortinet.plugin_rpc.start_rpc_listeners()


class LoadBalancerManager(driver_base.BaseLoadBalancerManager):

    @log_helpers.log_method_call
    def create(self, context, lb):
        self.driver.fortinet.loadbalancer.create(context, lb)

    @log_helpers.log_method_call
    def update(self, context, old_lb, lb):
        self.driver.fortinet.loadbalancer.update(context, old_lb, lb)

    @log_helpers.log_method_call
    def delete(self, context, lb):
        self.driver.fortinet.loadbalancer.delete(context, lb)

    @log_helpers.log_method_call
    def refresh(self, context, lb):
        self.driver.fortinet.loadbalancer.refresh(context, lb)

    @log_helpers.log_method_call
    def stats(self, context, lb):
        self.driver.fortinet.loadbalancer.stats(context, lb)
        # return self.driver.fortinet.loadbalancer.stats(context, lb)


class ListenerManager(driver_base.BaseListenerManager):

    @log_helpers.log_method_call
    def create(self, context, listener):
        self.driver.fortinet.listener.create(context, listener)

    @log_helpers.log_method_call
    def update(self, context, old_listener, listener):
        self.driver.fortinet.listener.update(context, old_listener, listener)

    @log_helpers.log_method_call
    def delete(self, context, listener):
        self.driver.fortinet.listener.delete(context, listener)


class PoolManager(driver_base.BasePoolManager):

    @log_helpers.log_method_call
    def create(self, context, pool):
        self.driver.fortinet.pool.create(context, pool)

    @log_helpers.log_method_call
    def update(self, context, old_pool, pool):
        self.driver.fortinet.pool.update(context, old_pool, pool)

    @log_helpers.log_method_call
    def delete(self, context, pool):
        self.driver.fortinet.pool.delete(context, pool)


class MemberManager(driver_base.BaseMemberManager):

    @log_helpers.log_method_call
    def create(self, context, member):
        self.driver.fortinet.member.create(context, member)

    @log_helpers.log_method_call
    def update(self, context, old_member, member):
        self.driver.fortinet.member.update(context, old_member, member)

    @log_helpers.log_method_call
    def delete(self, context, member):
        self.driver.fortinet.member.delete(context, member)


class HealthMonitorManager(driver_base.BaseHealthMonitorManager):

    @log_helpers.log_method_call
    def create(self, context, healthmonitor):
        self.driver.fortinet.healthmonitor.create(context, healthmonitor)

    @log_helpers.log_method_call
    def update(self, context, old_healthmonitor, healthmonitor):
        self.driver.fortinet.healthmonitor.update(context, old_healthmonitor,
                                                  healthmonitor)

    @log_helpers.log_method_call
    def delete(self, context, healthmonitor):
        self.driver.fortinet.healthmonitor.delete(context, healthmonitor)

# TODO: L7PolicyManager
# class L7PolicyManager(driver_base.BaseL7PolicyManager):
#
#     def create(self, context, l7policy):
#         LOG.debug('L7PolicyManager create')
#         LOG.debug(lb)
#         # self.driver.fortinet.l7policy.create(context, l7policy)
#
#     def update(self, context, old_l7policy, l7policy):
#         LOG.debug('L7PolicyManager update')
#         LOG.debug(lb)
#         # self.driver.fortinet.l7policy.update(context, old_l7policy, l7policy)
#
#     def delete(self, context, l7policy):
#         LOG.debug('L7PolicyManager delete')
#         LOG.debug(lb)
#         # self.driver.fortinet.l7policy.delete(context, l7policy)
#
# TODO: L7RuleManager
# class L7RuleManager(driver_base.BaseL7RuleManager):
#
#     def create(self, context, l7rule):
#         LOG.debug('L7RuleManager create')
#         LOG.debug(lb)
#         # self.driver.fortinet.l7rule.create(context, l7rule)
#
#     def update(self, context, old_l7rule, l7rule):
#         LOG.debug('L7RuleManager update')
#         LOG.debug(lb)
#         # self.driver.fortinet.l7rule.update(context, old_l7rule, l7rule)
#
#     def delete(self, context, l7rule):
#         LOG.debug('L7RuleManager delete')
#         LOG.debug(lb)
#         # self.driver.fortinet.l7rule.delete(context, l7rule)
