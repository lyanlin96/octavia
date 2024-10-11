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




from neutron.plugins.common import constants as plugin_constants
from neutron_lbaas.services.loadbalancer import constants as lb_constants
from neutron.common import rpc as n_rpc
import oslo_messaging
from oslo_log import helpers as log_helpers
from oslo_log import log as oslo_logging
LOG = oslo_logging.getLogger(__name__)

class LbaasV2PluginRpcApi(object):
    """Agent side of the Agent to Plugin RPC API."""

    # history
    #   1.0 Initial version

    def __init__(self, topic, context, host):
        self.context = context
        self.host = host
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target)
        LOG.debug("LbaasV2PluginRpcApi")

    def get_ready_devices(self):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'get_ready_devices', host=self.host)

    def get_error_devices(self):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'get_error_devices', host=self.host)
    def get_pending_delete_devices(self):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'get_pending_delete_devices', host=self.host)

    def get_loadbalancer(self, loadbalancer_id):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'get_loadbalancer',
                          loadbalancer_id=loadbalancer_id)

    def loadbalancer_deployed(self, loadbalancer_id):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'loadbalancer_deployed',
                          loadbalancer_id=loadbalancer_id)

    def update_status(self, obj_type, obj_id, provisioning_status=None,
                      operating_status=None):
        cctxt = self.client.prepare()
        LOG.debug("update_status")
        # obj_type = [loadbalancer, listener, pool, member, health_monitor]
        return cctxt.call(self.context, 'update_status', obj_type=obj_type,
                          obj_id=obj_id,
                          provisioning_status=provisioning_status,
                          operating_status=operating_status)

    # TODO List ???
    # snat --> db._core_plugin.update_port
    # add_allowed_address  --> db._core_plugin.update_port
    # remove_allowed_address  --> db._core_plugin.update_port
    def plug_vip_port(self, port_id):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'plug_vip_port', port_id=port_id,
                          host=self.host)

    def unplug_vip_port(self, port_id):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'unplug_vip_port', port_id=port_id,
                          host=self.host)


    @log_helpers.log_method_call
    def update_loadbalancer_stats(self, loadbalancer_id, stats):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'update_loadbalancer_stats',
                          loadbalancer_id=loadbalancer_id, stats=stats)

    @log_helpers.log_method_call
    def loadbalancer_destroyed(self, loadbalancer_id=None):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'loadbalancer_destroyed',
                          loadbalancer_id=loadbalancer_id)

    @log_helpers.log_method_call
    def update_listener_status(self,
                               listener_id,
                               provisioning_status=plugin_constants.ERROR,
                               operating_status=lb_constants.OFFLINE):
        """Update the database with listener status."""
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'update_listener_status',
                           listener_id=listener_id,
                           provisioning_status=provisioning_status,
                          operating_status=operating_status)

    @log_helpers.log_method_call
    def listener_destroyed(self, listener_id):
        """Delete listener from database."""
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'listener_destroyed',
                          listener_id=listener_id)

    @log_helpers.log_method_call
    def pool_destroyed(self, pool_id):
        """Delete pool from database."""
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'pool_destroyed',
                          pool_id=pool_id)

    @log_helpers.log_method_call
    def member_destroyed(self, member_id):
        """Delete member from database."""
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'member_destroyed',
                          member_id=member_id)

    @log_helpers.log_method_call
    def healthmonitor_destroyed(self, healthmonitor_id):
        """Delete healthmonitor from database."""
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'healthmonitor_destroyed',
                          healthmonitor_id=healthmonitor_id)

