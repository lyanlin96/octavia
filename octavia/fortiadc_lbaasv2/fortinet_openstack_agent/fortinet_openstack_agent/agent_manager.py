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
from neutron.agent import rpc as agent_rpc
from neutron_lib import context as ncontext
from neutron_lbaas.services.loadbalancer import constants as lb_constants
from neutron_lbaas.services.loadbalancer import data_models
from neutron_lib import constants
from neutron_lib import exceptions as n_exc
from neutron.plugins.common import constants as plugin_constants
import oslo_messaging
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_utils import importutils
from oslo_concurrency import lockutils

from fortinet_openstack_agent import constants as agent_constants
from fortinet_openstack_agent import plugin_rpc
from fortinet_openstack_agent import exceptions as f_exceptions


LOG = logging.getLogger(__name__)

DEVICE_DRIVERS = 'device_drivers'
driver_name = agent_constants.DRIVER_NAME

OPTS = [
    cfg.StrOpt(
        'device_driver',
        default=('fortinet_openstack_agent.fadc_device_driver.FadcdeviceDriver'),
        help=('Drivers used to manage loadbalancing devices'),
    ),
]

class DeviceNotFoundOnAgent(n_exc.NotFound):
    message = _('Unknown device with loadbalancer_id %(loadbalancer_id)s')


class LbaasAgentManager(periodic_task.PeriodicTasks):
    """Periodic task that is an endpoint for plugin to agent RPC."""

    RPC_API_VERSION = '1.0'

    target = oslo_messaging.Target(version='1.0')

    def __init__(self, conf):
        """Initialize LbaasAgentManager."""
        super(LbaasAgentManager, self).__init__(conf)
        LOG.debug("Initializing LbaasAgentManager")

        self.conf = conf
        self.context = ncontext.get_admin_context_without_session()
        self.serializer = None

        self.plugin_rpc = plugin_rpc.LbaasV2PluginRpcApi(
            agent_constants.TOPIC_LOADBALANCER_PLUGIN_V2,
            self.context,
            self.conf.host
        )
        self._load_drivers()
        self.driver = self.device_drivers[driver_name] if self.device_drivers else None
        self.device_data = {
            driver_name: {'loadbalancer': [], 'listener': [], 'pool': [], 'member': [], 'health_monitor': []}}

        # Initialize agent-state
        self.agent_state = {
            'binary': agent_constants.AGENT_NAME,
            'host': conf.host,
            'topic': agent_constants.TOPIC_LOADBALANCER_AGENT_V2,
            'configurations': {
                'device_drivers': [driver_name],
                'report_interval': self.conf.AGENT.report_interval,
            },
            'agent_type': lb_constants.AGENT_TYPE_LOADBALANCERV2,
            'start_flag': True
        }
        self.admin_state_up = True

        self._setup_state_rpc()
        self.needs_resync = False
        self.instance_mapping = {}
        # tenants_lb { tenant_id : [lb_id] }
        self.tenants_lb = {}
        self.tenants_lb_lock = lockutils.ReaderWriterLock()
        self.lb_pending_delete_num = 0
        self.lb_pending_delete_num_lock = lockutils.ReaderWriterLock()
 
        self.lock = lockutils.ReaderWriterLock()
        self.active_num = 0
        self.need_update_token = False

        # Fill with loadbalancer id for debug init ex: init_ids = [ 'LB_ID_1', 'LB_ID_2' ]
        init_ids = []
        for init_id in init_ids:
            self.instance_mapping[init_id] = driver_name
            self._tenants_lb_push(loadbalancer_id=init_id)
            self.plugin_rpc.loadbalancer_deployed(init_id)

    def _load_drivers(self):
        self.device_drivers = {}

        LOG.debug("import fadc device driver %s\n", self.conf.device_driver)
        if True:
        #try:
            driver_inst = importutils.import_object(
                self.conf.device_driver,
                self.conf,
            )
        #except ImportError:
        #    msg = _('Error importing loadbalancer device driver')
        #    raise SystemExit(msg)

        driver_name = driver_inst.get_name()
        if driver_name not in self.device_drivers:
            self.device_drivers[driver_name] = driver_inst
        else:
            msg = _('Multiple device drivers with the same name found: %s')
            raise SystemExit(msg % driver_name)


    def _setup_state_rpc(self):
        self.state_rpc = agent_rpc.PluginReportStateAPI(
            agent_constants.TOPIC_LOADBALANCER_PLUGIN_V2)
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)

    def _report_state(self):
        try:
            instance_count = len(self.instance_mapping)
            self.agent_state['configurations']['instances'] = instance_count
            self.state_rpc.report_state(self.context, self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception:
            LOG.exception("Failed reporting state!")

    def initialize_service_hook(self, started_by):
        """Create service hook to listen for messanges on agent topic."""
        # listen topic.host
        node_topic = '%s.%s' % (agent_constants.TOPIC_LOADBALANCER_AGENT_V2, self.conf.host)
        LOG.debug("Creating topic for consuming messages: %s" % node_topic)
        endpoints = [started_by.manager]
        LOG.debug(endpoints)
        started_by.conn.create_consumer(
            node_topic, endpoints, fanout=False)
        self.sync_state()


    def _refresh_device_driver(self, context):
        with self.lock.write_lock():
            if (self.active_num == 0):
                driver = self.device_drivers[driver_name]
                try:
                    driver.refresh()
                    self.need_update_token = False
                except Exception:
                    LOG.warning("Refesh token failed. Token may expired soon\n")
                    self.need_update_token = True
 
    @periodic_task.periodic_task(spacing=12600)
    def refresh_device_driver(self, context):
        self._refresh_device_driver(context)

    @periodic_task.periodic_task
    def periodic_resync(self, context):
        # needs_resync would be true when something error
        if self.need_update_token:
            self._refresh_device_driver(context)

        if self.needs_resync:
            with self.lock.write_lock():
                self.active_num += 1
            self.needs_resync = False
            self.sync_state()
            with self.lock.write_lock():
                self.active_num += -1

    @periodic_task.periodic_task(spacing=6)
    def collect_stats(self, context):
        with self.lb_pending_delete_num_lock.write_lock():
            if self.lb_pending_delete_num == 0:
                with self.lock.write_lock():
                    self.active_num += 1
                self._collect_stats(context)
                with self.lock.write_lock():
                    self.active_num += -1

    def _collect_stats(self, context):

        for loadbalancer_id, driver_name in self.instance_mapping.items():
            driver = self.device_drivers[driver_name]
            try:
                lb = self.plugin_rpc.get_loadbalancer(loadbalancer_id)
                lb = data_models.LoadBalancer.from_dict(lb)
                if lb.provisioning_status == "ACTIVE":
                    stats = driver.loadbalancer.get_stats(lb)
                    if stats:
                        self.plugin_rpc.update_loadbalancer_stats(
                            loadbalancer_id, stats)
                    else:
                        self.needs_resync = True
            except Exception:
                LOG.exception(('Error updating statistics on loadbalancer'
                               ' %s'),
                              loadbalancer_id)
                self.needs_resync = True
            if lb.provisioning_status == "ACTIVE":
                try:
                    member_healthy_mapping = {
                        'HEALTHY': constants.ACTIVE,
                        'UNHEALTHY': constants.INACTIVE,
                        'MAINTAINED': constants.INACTIVE,
                        'DISABLE': constants.INACTIVE,
                        'NO_HEALTH_CHECK': None
                    }
                    for pool in lb.pools:
                        if pool.healthmonitor_id:
                            for member in pool.members:
                                device_member_availability = driver.member.get_member_availability(member)
                                if device_member_availability and member_healthy_mapping[device_member_availability] and member_healthy_mapping[
                                    device_member_availability] != member.provisioning_status:
                                    self.plugin_rpc.update_status('member', member.id,
                                                                  provisioning_status=member_healthy_mapping[
                                                                      device_member_availability],
                                                                  operating_status=None)
                except Exception:
                    LOG.exception('Error updating status on member')
                    self.needs_resync = True


    def sync_state(self):
        """sync state when the service start or periodic_resync"""

        known_instances = set(self.instance_mapping.keys())
        try:
            ready_instances = set(self.plugin_rpc.get_ready_devices())
            for loadbalancer_id in ready_instances:
                self._reload_loadbalancer(loadbalancer_id)

            error_instances =set (self.plugin_rpc.get_error_devices())
            for loadbalancer_id in error_instances:
                self.instance_mapping[loadbalancer_id] = driver_name
                self._tenants_lb_push(loadbalancer_id = loadbalancer_id)

            pending_delete_instances = set (self.plugin_rpc.get_pending_delete_devices())
            for loadbalancer_id in pending_delete_instances:
                self.instance_mapping[loadbalancer_id] = driver_name
                self._tenants_lb_push(loadbalancer_id = loadbalancer_id)
                self._destroy_loadbalancer(loadbalancer_id)

        except Exception:
            LOG.exception('Unable to retrieve or sync devices')
            self.needs_resync = True


    def _get_driver(self, loadbalancer_id):
        if loadbalancer_id not in self.instance_mapping:
            raise DeviceNotFoundOnAgent(loadbalancer_id=loadbalancer_id)

        driver_name = self.instance_mapping[loadbalancer_id]
        return self.device_drivers[driver_name]

    def _reload_loadbalancer(self, loadbalancer_id):
        try:
            loadbalancer_dict = self.plugin_rpc.get_loadbalancer(
                loadbalancer_id)
            loadbalancer = data_models.LoadBalancer.from_dict(
                loadbalancer_dict)
            driver_name = loadbalancer.provider.device_driver
            if driver_name not in self.device_drivers:
                LOG.error('No device driver on agent: %s.' %(driver_name))
                self.plugin_rpc.update_status(
                    'loadbalancer', loadbalancer_id, constants.ERROR)
                return

            self.device_drivers[driver_name].deploy_instance(loadbalancer)
            self.instance_mapping[loadbalancer_id] = driver_name
            # loadbalancer_deployed sets all status to ACTIVE
            self.plugin_rpc.loadbalancer_deployed(loadbalancer_id)
            self._tenants_lb_push(loadbalancer)
        except Exception:
            LOG.exception('Unable to deploy instance for loadbalancer: %s' %(loadbalancer_id))
            self.plugin_rpc.update_status('loadbalancer', loadbalancer_id, constants.ERROR)
            self.instance_mapping[loadbalancer_id] = driver_name
            self._tenants_lb_push(loadbalancer_id=loadbalancer_id)
            self.needs_resync = True

    def _destroy_loadbalancer(self, loadbalancer_id):
        try:
            loadbalancer = self.plugin_rpc.get_loadbalancer(
                loadbalancer_id)
            self.delete_loadbalancer(None, loadbalancer)

        except Exception:
            LOG.exception('Unable to destroy instance for loadbalancer: %s' %(loadbalancer_id))
            self.plugin_rpc.update_status('loadbalancer', loadbalancer_id, constants.ERROR)
            self.needs_resync = True

    def remove_orphans(self):
        for driver_name in self.device_drivers:
            lb_ids = [lb_id for lb_id in self.instance_mapping
                      if self.instance_mapping[lb_id] == driver_name]
            try:
                #self.device_drivers[driver_name].remove_orphans(lb_ids)  # TODO: call device_driver.remove_orphans
                for lb_id in lb_ids:
                    del self.instance_mapping[lb_id]
                    self._tenants_lb_pop(loadbalancer_id=lb_id)
            except NotImplementedError:
                pass  # Not all drivers will support this

    def _handle_failed_driver_call(self, operation, obj, driver):
        obj_type = obj.__class__.__name__.lower()
        LOG.exception('%(operation)s %(obj)s %(id)s failed on device '
                      'driver %(driver)s',
                      {'operation': operation.capitalize(), 'obj': obj_type,
                       'id': obj.id, 'driver': driver})
        self._update_statuses(obj, error=True)

    def _update_statuses(self, obj, error=False):
        """ update the obj and its loadbalancer status """
        lb_p_status = constants.ACTIVE
        lb_o_status = None
        obj_type = obj.__class__.__name__.lower()
        obj_p_status = constants.ACTIVE
        obj_o_status = lb_constants.ONLINE
        if error:
            obj_p_status = constants.ERROR
            obj_o_status = lb_constants.OFFLINE
        if isinstance(obj, data_models.HealthMonitor):
            obj_o_status = None
        if isinstance(obj, data_models.LoadBalancer):
            lb_o_status = lb_constants.ONLINE
            if error:
                lb_p_status = constants.ERROR
                lb_o_status = lb_constants.OFFLINE
            lb = obj
        else:
            lb = obj.root_loadbalancer
            self.plugin_rpc.update_status(obj_type, obj.id,
                                          provisioning_status=obj_p_status,
                                          operating_status=obj_o_status)
        self.plugin_rpc.update_status('loadbalancer', lb.id,
                                      provisioning_status=lb_p_status,
                                      operating_status=lb_o_status)

    def _update_obj_loadbalancer_status(self, obj, error=False):
        """ update the loadbalancer_status of the obj """
        lb_p_status = constants.ACTIVE
        lb_o_status = None
        if isinstance(obj, data_models.LoadBalancer):
            lb_o_status = lb_constants.ONLINE
            if error:
                lb_p_status = constants.ERROR
                lb_o_status = lb_constants.OFFLINE
            lb = obj
        else:
            lb = obj.root_loadbalancer

        self.plugin_rpc.update_status('loadbalancer', lb.id,
                                      provisioning_status=lb_p_status,
                                      operating_status=lb_o_status)

    def _lb_pending_delete_num(self, addend=0):
        """ only protect the lb_pending_delete_num
        single lock
            1. lb_pending_delete_num_lock

        :param addend: addend to the number of lb_pending_delete
        :return: the result of number of lb_pending_delete
        """
        with self.lb_pending_delete_num_lock.write_lock():
            self.lb_pending_delete_num += addend
            return self.lb_pending_delete_num

    def _tenants_lb_pop(self, loadbalancer=None, loadbalancer_id=None):
        if loadbalancer:
            lb = loadbalancer
        elif loadbalancer_id:
            lb = self.plugin_rpc.get_loadbalancer(loadbalancer_id)
            lb = data_models.LoadBalancer.from_dict(lb)
        else:
            LOG.error("No loadbalancer to do tenants_lb_pop")
            return -1

        with self.tenants_lb_lock.write_lock():
            tenants_lb_num = 0
            if self.tenants_lb.has_key(lb.tenant_id):
                if self.tenants_lb[lb.tenant_id].count(lb.id) > 0:
                    self.tenants_lb[lb.tenant_id].remove(lb.id)
                    tenants_lb_num = len(self.tenants_lb[lb.tenant_id])
                    if tenants_lb_num == 0:
                        del self.tenants_lb[lb.tenant_id]
            return tenants_lb_num


    def _tenants_lb_push(self, loadbalancer=None, loadbalancer_id=None):
        if loadbalancer:
            lb = loadbalancer
        elif loadbalancer_id:
            lb = self.plugin_rpc.get_loadbalancer(loadbalancer_id)
            lb = data_models.LoadBalancer.from_dict(lb)
        else:
            LOG.error("No loadbalancer to do tenants_lb_push")
            return -1

        with self.tenants_lb_lock.write_lock():
            if self.tenants_lb.has_key(lb.tenant_id):
                # One tenant has loadbalances witch have different unique id
                if self.tenants_lb[lb.tenant_id].count(lb.id) == 0:
                    self.tenants_lb[lb.tenant_id].append(lb.id)
            else:
                # The first lb belong to the tenant
                self.tenants_lb[lb.tenant_id] = [lb.id]
            return len(self.tenants_lb[lb.tenant_id])

    @log_helpers.log_method_call
    def create_loadbalancer(self, context, loadbalancer):
        """ Create LoadBalancer """

        with self.lock.write_lock():
            self.active_num += 1
        loadbalancer = data_models.LoadBalancer.from_dict(loadbalancer)
        driver = self.device_drivers[driver_name]
        try:
            driver.loadbalancer.create(loadbalancer)
        except Exception:
            self._handle_failed_driver_call('create', loadbalancer,
                                            driver.get_name())
        else:
            self.instance_mapping[loadbalancer.id] = driver_name
            self._tenants_lb_push(loadbalancer)
            self._update_statuses(loadbalancer)

        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def update_loadbalancer(self, context, old_loadbalancer, loadbalancer):
        with self.lock.write_lock():
            self.active_num += 1
        self.plugin_rpc.update_status('loadbalancer', loadbalancer['id'],
                                      provisioning_status=plugin_constants.ACTIVE)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def delete_loadbalancer(self, context, loadbalancer):
        """Handle RPC cast from plugin to delete_loadbalancer."""
        with self.lock.write_lock():
            self.active_num += 1
        self._lb_pending_delete_num(1)
        loadbalancer = data_models.LoadBalancer.from_dict(loadbalancer)
        try:
            #sys.exit()
            driver = self._get_driver(loadbalancer.id)
            #check if other load balancers are shared in the same tenant
            if self._tenants_lb_pop(loadbalancer) == 0:
                # delete vdom
                driver.loadbalancer.delete(loadbalancer)
        except DeviceNotFoundOnAgent:
            self.plugin_rpc.loadbalancer_destroyed(loadbalancer.id)
        except f_exceptions.NotFoundException:
            del self.instance_mapping[loadbalancer.id]
            self._tenants_lb_pop(loadbalancer)
            self.plugin_rpc.loadbalancer_destroyed(loadbalancer.id)
        except Exception:
            self._tenants_lb_push(loadbalancer)
            self._handle_failed_driver_call('delete', loadbalancer,
                                            driver.get_name())
        else:
            del self.instance_mapping[loadbalancer.id]
            self.plugin_rpc.loadbalancer_destroyed(loadbalancer.id)

        self._lb_pending_delete_num(-1)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def create_listener(self, context, listener):
        """ Create Listencer """

        with self.lock.write_lock():
            self.active_num += 1
        listener = data_models.Listener.from_dict(listener)

        try:
            driver = self._get_driver(listener.loadbalancer.id)
            driver.listener.create(listener)
        except Exception:
            self._handle_failed_driver_call('create', listener,
                                            driver.get_name())
        else:
            self._update_statuses(listener)

        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def update_listener(self, context, old_listener, listener):
        """ Update Listencer """

        with self.lock.write_lock():
            self.active_num += 1
        listener = data_models.Listener.from_dict(listener)
        old_listener = data_models.Listener.from_dict(old_listener)
        driver = self.device_drivers[driver_name]
        try:
            driver.listener.update(old_listener, listener)
        except Exception:
            self._handle_failed_driver_call('update', listener,
                                            driver.get_name())
        else:
            self._update_statuses(listener)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def delete_listener(self, context, listener):
        """Handle RPC cast from plugin to delete_listener."""

        with self.lock.write_lock():
            self.active_num += 1
        listener = data_models.Listener.from_dict(listener)

        try:
            driver = self._get_driver(listener.loadbalancer.id)
            driver.listener.delete(listener)
        except DeviceNotFoundOnAgent:
            self.plugin_rpc.listener_destroyed(listener.id)
            self._update_obj_loadbalancer_status(listener)
        except f_exceptions.NotFoundException:
            self.plugin_rpc.listener_destroyed(listener.id)
            self._update_obj_loadbalancer_status(listener)
        except Exception:
            self._handle_failed_driver_call('delete', listener,
                                            driver.get_name())
        else:
            self.plugin_rpc.listener_destroyed(listener.id)
            self._update_obj_loadbalancer_status(listener)
        with self.lock.write_lock():
            self.active_num += -1


    @log_helpers.log_method_call
    def create_pool(self, context, pool):
        """ Create Pool """

        with self.lock.write_lock():
            self.active_num += 1
        pool = data_models.Pool.from_dict(pool)

        driver = self.device_drivers[driver_name]

        try:
            driver.pool.create(pool)
        except Exception:
            self._handle_failed_driver_call('create', pool,
                                            driver.get_name())
        else:
            if pool.listener:
                try:
                    listener = data_models.Listener.from_dict(pool.listener)
                    listener.default_pool = pool
                    driver.listener.create(listener)
                except Exception:
                    LOG.error("create listener failed")
            self._update_statuses(pool)

        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def update_pool(self, context, old_pool, pool):
        """ Update Pool """

        with self.lock.write_lock():
            self.active_num += 1
        pool = data_models.Pool.from_dict(pool)
        old_pool = data_models.Pool.from_dict(old_pool)
        driver = self.device_drivers[driver_name]
        try:
            if old_pool.lb_algorithm != pool.lb_algorithm:
                for listener in pool.listeners:
                    listener.default_pool = pool
                    driver.listener.update(None, listener)
        except Exception:
            self._handle_failed_driver_call('update', pool,
                                            driver.get_name())
        else:
            self._update_statuses(pool)

        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def delete_pool(self, context, pool):
        """Handle RPC cast from plugin to delete_pool."""

        with self.lock.write_lock():
            self.active_num += 1
        pool = data_models.Pool.from_dict(pool)

        try:
            driver = self._get_driver(pool.loadbalancer.id)
            for listener in pool.listeners:
                driver.listener.delete(listener)
            for member in pool.members:
                driver.member.delete(member)
            driver.pool.delete(pool)
        except DeviceNotFoundOnAgent:
            self.plugin_rpc.pool_destroyed(pool.id)
            self._update_obj_loadbalancer_status(pool)
        except f_exceptions.NotFoundException:
            self.plugin_rpc.pool_destroyed(pool.id)
            self._update_obj_loadbalancer_status(pool)
        except Exception:
            self._handle_failed_driver_call('delete', pool,
                                            driver.get_name())
        else:
            self.plugin_rpc.pool_destroyed(pool.id)
            self._update_obj_loadbalancer_status(pool)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def create_member(self, context, member):
        """ Create Member """

        with self.lock.write_lock():
            self.active_num += 1
        member = data_models.Member.from_dict(member)

        driver = self.device_drivers[driver_name]
        try:
            driver.member.create(member)
        except Exception:
            self._handle_failed_driver_call('create', member,
                                            driver.get_name())
        else:
            self._update_statuses(member)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def update_member(self, context, old_member, member):
        """ Update Member """

        with self.lock.write_lock():
            self.active_num += 1
        member = data_models.Member.from_dict(member)
        old_member = data_models.Member.from_dict(old_member)
        driver = self.device_drivers[driver_name]
        try:
            driver.member.update(old_member, member)
        except Exception:
            self._handle_failed_driver_call('update', member,
                                            driver.get_name())
        else:
            self._update_statuses(member)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def delete_member(self, context, member):
        """Handle RPC cast from plugin to delete_member."""

        with self.lock.write_lock():
            self.active_num += 1
        member = data_models.Member.from_dict(member)

        try:
            driver = self._get_driver(member.pool.loadbalancer.id)
            driver.member.delete(member)
        except DeviceNotFoundOnAgent:
            self.plugin_rpc.member_destroyed(member.id)
            self._update_obj_loadbalancer_status(member)
        except f_exceptions.NotFoundException:
            self.plugin_rpc.member_destroyed(member.id)
            self._update_obj_loadbalancer_status(member)
        except Exception:
            self._handle_failed_driver_call('delete', member,
                                            driver.get_name())
        else:
            self.plugin_rpc.member_destroyed(member.id)
            self._update_obj_loadbalancer_status(member)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def create_healthmonitor(self, context, healthmonitor):
        with self.lock.write_lock():
            self.active_num += 1
        healthmonitor = data_models.HealthMonitor.from_dict(healthmonitor)

        try:
            driver = self._get_driver(healthmonitor.pool.loadbalancer.id)
            driver.healthmonitor.create(healthmonitor)
        except Exception:
            self._handle_failed_driver_call('create', healthmonitor,
                                            driver.get_name())
        else:
            self._update_statuses(healthmonitor)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def update_healthmonitor(self, context, old_healthmonitor, healthmonitor):
        """ Update Health Monitor """

        with self.lock.write_lock():
            self.active_num += 1
        healthmonitor = data_models.HealthMonitor.from_dict(healthmonitor)
        old_healthmonitor = data_models.HealthMonitor.from_dict(old_healthmonitor)
        driver = self.device_drivers[driver_name]
        try:
            driver.healthmonitor.update(old_healthmonitor, healthmonitor)
        except Exception:
            self._handle_failed_driver_call('update', healthmonitor,
                                            driver.get_name())
        else:
            self._update_statuses(healthmonitor)
        with self.lock.write_lock():
            self.active_num += -1

    @log_helpers.log_method_call
    def delete_healthmonitor(self, context, healthmonitor):
        """Handle RPC cast from plugin to delete_healthmonitor."""

        with self.lock.write_lock():
            self.active_num += 1
        healthmonitor = data_models.HealthMonitor.from_dict(healthmonitor)

        try:
            driver = self._get_driver(healthmonitor.pool.loadbalancer.id)
            driver.healthmonitor.delete(healthmonitor)
        except DeviceNotFoundOnAgent:
            self.plugin_rpc.healthmonitor_destroyed(healthmonitor.id)
            self._update_obj_loadbalancer_status(healthmonitor)
        except f_exceptions.NotFoundException:
            self.plugin_rpc.healthmonitor_destroyed(healthmonitor.id)
            self._update_obj_loadbalancer_status(healthmonitor)
        except Exception:
            self._handle_failed_driver_call('delete', healthmonitor,
                                            driver.get_name())
        else:
            self.plugin_rpc.healthmonitor_destroyed(healthmonitor.id)
            self._update_obj_loadbalancer_status(healthmonitor)
        with self.lock.write_lock():
            self.active_num += -1

