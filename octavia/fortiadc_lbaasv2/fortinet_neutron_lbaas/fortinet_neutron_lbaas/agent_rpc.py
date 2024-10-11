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

import oslo_messaging
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)

class LbaasV2AgentRpc(object):
    """Agent side of the Agent to Plugin RPC API."""

    # history
    #   1.0 Initial version

    def __init__(self, topic):
        # self.host = host # ??
        self.topic = topic
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target, version_cap=None)


    @log_helpers.log_method_call
    def create_loadbalancer(self, context, loadbalancer, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'create_loadbalancer', loadbalancer=loadbalancer)


    @log_helpers.log_method_call
    def update_loadbalancer(self, context, old_loadbalancer, loadbalancer, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'update_loadbalancer', old_loadbalancer=old_loadbalancer, loadbalancer=loadbalancer)


    @log_helpers.log_method_call
    def delete_loadbalancer(self, context, loadbalancer, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'delete_loadbalancer', loadbalancer=loadbalancer)


    @log_helpers.log_method_call
    def update_loadbalancer_stats(self, context, loadbalancer, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'update_loadbalancer_stats', loadbalancer=loadbalancer)


    @log_helpers.log_method_call
    def create_listener(self, context, listener, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'create_listener', listener=listener)


    @log_helpers.log_method_call
    def update_listener(self, context, old_listener, listener, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'update_listener', old_listener=old_listener, listener=listener)


    @log_helpers.log_method_call
    def delete_listener(self, context, listener, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'delete_listener', listener=listener)


    @log_helpers.log_method_call
    def create_pool(self, context, pool, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'create_pool', pool=pool)


    @log_helpers.log_method_call
    def update_pool(self, context, old_pool, pool, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'update_pool', old_pool=old_pool, pool=pool)


    @log_helpers.log_method_call
    def delete_pool(self, context, pool, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'delete_pool', pool=pool)


    @log_helpers.log_method_call
    def create_member(self, context, member, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'create_member', member=member)


    @log_helpers.log_method_call
    def update_member(self, context, old_member, member, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'update_member', old_member=old_member, member=member)


    @log_helpers.log_method_call
    def delete_member(self, context, member, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'delete_member', member=member)


    @log_helpers.log_method_call
    def create_healthmonitor(self, context, healthmonitor, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'create_healthmonitor', healthmonitor=healthmonitor)


    @log_helpers.log_method_call
    def update_healthmonitor(self, context, old_healthmonitor, healthmonitor, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'update_healthmonitor', old_healthmonitor=old_healthmonitor, healthmonitor=healthmonitor)


    @log_helpers.log_method_call
    def delete_healthmonitor(self, context, healthmonitor, host=None):
        topic = self.topic if host is None else '%s.%s' % (self.topic, host)
        cctxt = self.client.prepare(topic=topic)
        return cctxt.cast(context, 'delete_healthmonitor', healthmonitor=healthmonitor)

