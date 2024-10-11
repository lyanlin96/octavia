
import copy
from cryptography import fernet
from oslo_config import cfg
from oslo_log import log as logging
from stevedore import driver as stevedore_driver
from taskflow import retry
from taskflow import task
from taskflow.types import failure

#from octavia.amphorae.backends.agent import agent_jinja_cfg
#from octavia.amphorae.driver_exceptions import exceptions as driver_except
from octavia.common import constants
from octavia.common import utils
from octavia.common import data_models
from octavia.controller.worker import task_utils as task_utilities
from octavia.db import api as db_apis
from octavia.db import repositories as repo
#from octavia.network import data_models
from octavia_lib.api.drivers import driver_lib
from octavia_lib.api.drivers import exceptions as driver_exceptions
from octavia_lib.common import constants as lib_consts
from fadc_octavia_provider.fortiadc_agent.fadc_device_driver import FadcdeviceDriver

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class BaseFortiadcTask(task.Task):
    """Base task to load drivers common to the tasks."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.listener_repo = repo.ListenerRepository()
        self.loadbalancer_repo = repo.LoadBalancerRepository()
        self.member_repo = repo.MemberRepository()
        self.pool_repo = repo.PoolRepository()
        self.health_mon_repo = repo.HealthMonitorRepository()
        self.task_utils = task_utilities.TaskUtils()
        #self.fadc_device_driver = FadcdeviceDriver(CONF)

    def update_status(self, loadbalancer_id):
        o_driver_lib = driver_lib.DriverLibrary(
            status_socket=CONF.driver_agent.status_socket_path,
            stats_socket=CONF.driver_agent.stats_socket_path,
            get_socket=CONF.driver_agent.get_socket_path,
        )

        db_lb = self.loadbalancer_repo.get(db_apis.get_session(), id=loadbalancer_id)
        lb_status = {constants.LOADBALANCERS: [{'id': db_lb.id}]}
        lb_status[constants.LOADBALANCERS][0][lib_consts.OPERATING_STATUS] = lib_consts.ONLINE
        listeners_status = []
        pools_status = []
        members_status = []

        lb_status['listeners'] = listeners_status
        lb_status['pools'] = pools_status
        lb_status['members'] = members_status

        if db_lb.listeners:
            for listener in db_lb.listeners:
                listeners_status.append({'id': listener.id, lib_consts.OPERATING_STATUS: lib_consts.ONLINE})
        if db_lb.pools:
            for pool in db_lb.pools:
                pools_status.append({'id': pool.id, lib_consts.OPERATING_STATUS: lib_consts.ONLINE})
                for member in pool.members:
                    members_status.append({'id': member.id, lib_consts.OPERATING_STATUS: lib_consts.ONLINE})

        o_driver_lib.update_loadbalancer_status(lb_status)


class FortiadcRetry(retry.Times):

    def on_failure(self, history, *args, **kwargs):
        last_errors = history[-1][1]
        max_retry_attempt = CONF.haproxy_amphora.connection_max_retries
        for task_name, ex_info in last_errors.items():
            if len(history) <= max_retry_attempt:
                # When taskflow persistance is enabled and flow/task state is
                # saved in the backend. If flow(task) is restored(restart of
                # worker,etc) we are getting ex_info as None - we need to RETRY
                # task to check its real state.
                if ex_info is None or ex_info._exc_info is None:
                    return retry.RETRY
                excp = ex_info._exc_info[1]
                if isinstance(excp, driver_except.AmpConnectionRetry):
                    return retry.RETRY

        return retry.REVERT_ALL


class LoadBalancerCreate(BaseFortiadcTask):

    def execute(self, loadbalancer, topology=None, project_id=None, listeners=None, pool=None):
        LOG.debug("task:LoadBalancerCreate: execute, %s", loadbalancer)
        #lb_obj = data_models.LoadBalancer.from_dict(loadbalancer)
        db_lb = self.loadbalancer_repo.get(db_apis.get_session(), id=loadbalancer['loadbalancer_id'])
        FadcdeviceDriver(CONF, project_id = loadbalancer['project_id']).loadbalancer.create(db_lb)

    def revert(self, loadbalancer, *args, **kwargs):
        LOG.warning("task:LoadBalancerCreate: revert")


class LoadBalancerDelete(BaseFortiadcTask):

    def execute(self, loadbalancer):
        LOG.debug("task:LoadBalancerDelete: execute")
        FadcdeviceDriver(CONF, project_id = loadbalancer['project_id']).loadbalancer.delete(loadbalancer)

    def revert(self, loadbalancer, *args, **kwargs):
        LOG.warning("task:LoadBalancerDelete: revert")

class LoadBalancerUnplug(BaseFortiadcTask):

    def execute(self, loadbalancer):
        LOG.debug("task:LoadBalancerUnplug: execute")
        FadcdeviceDriver(CONF, project_id = loadbalancer['project_id']).loadbalancer.unplug(loadbalancer)

    def revert(self, loadbalancer, *args, **kwargs):
        LOG.warning("task:LoadBalancerUnplug: revert")

class ListenerCreate(BaseFortiadcTask):

    def execute(self, listeners):
        LOG.debug("task:ListenerCreate: execute, %s", listeners)
        #lb_obj = data_models.LoadBalancer.from_dict(loadbalancer)
        for listener in listeners:
            db_listener = self.listener_repo.get(db_apis.get_session(), id = listener[constants.LISTENER_ID])
            LOG.debug("task:ListenerCreate: execute, %s", repr(db_listener))
            FadcdeviceDriver(CONF, project_id = db_listener.project_id).listener.create(db_listener)

    def revert(self, listeners, *args, **kwargs):
        LOG.warning("task:ListenerCreate: revert")


class ListenerDelete(BaseFortiadcTask):

    def execute(self, listener):
        LOG.debug("task:LisenerDelete: execute")
        db_listener = self.listener_repo.get(db_apis.get_session(), id = listener[constants.LISTENER_ID])
        FadcdeviceDriver(CONF, project_id = db_listener.project_id).listener.delete(db_listener)

    def revert(self, listener, *args, **kwargs):
        LOG.warning("task:ListenerDelete: revert")

class ListenersUpdate(BaseFortiadcTask):

    def execute(self, loadbalancer_id):
        loadbalancer = self.loadbalancer_repo.get(db_apis.get_session(),
                                                  id=loadbalancer_id)
        LOG.debug("task:ListenerUpdate: execute")
        if loadbalancer:
            for listener in loadbalancer.listeners:
                LOG.debug('task:listenersUpdate: listener is %s', listener.to_dict())
                FadcdeviceDriver(CONF, project_id = listener.project_id).listener.update(listener)
        else:
            LOG.error('Load balancer %s for listeners update not found. '
                      'Skipping update.', loadbalancer_id)

    def revert(self, loadbalancer_id, *args, **kwargs):

        LOG.warning("Reverting listeners updates.")
        loadbalancer = self.loadbalancer_repo.get(db_apis.get_session(),
                                                  id=loadbalancer_id)
        for listener in loadbalancer.listeners:
            self.task_utils.mark_listener_prov_status_error(
                listener.id)

class PoolCreate(BaseFortiadcTask):

    def execute(self, pool_id, listeners):
        LOG.debug("task:PoolCreate: execute, %s, %s", pool_id, listeners)
        #lb_obj = data_models.LoadBalancer.from_dict(loadbalancer)
        db_pool = self.pool_repo.get(db_apis.get_session(), id = pool_id)
        
        LOG.debug("task:PoolCreate: execute, %s", repr(db_pool))
        FadcdeviceDriver(CONF, project_id = db_pool.project_id).pool.create(db_pool)

        for listener in listeners:
            if listener[constants.LISTENER_ID]:
                db_listener = self.listener_repo.get(db_apis.get_session(), id = listener[constants.LISTENER_ID])
                LOG.debug("task:PoolCreate: vip is %s", db_listener.load_balancer.vip.ip_address)
                FadcdeviceDriver(CONF, project_id = db_listener.project_id).listener.create(db_listener)

    def revert(self, pool_id, listeners, *args, **kwargs):
        LOG.warning("task:PoolCreate: revert")


class PoolDelete(BaseFortiadcTask):

    def execute(self, pool_id):
        LOG.debug("task:PoolDelete: execute")
        db_pool = self.pool_repo.get(db_apis.get_session(), id = pool_id)
        FadcdeviceDriver(CONF, project_id = db_pool.project_id).pool.delete(db_pool)

    def revert(self, pool_id, *args, **kwargs):
        LOG.warning("task:PoolDelete: revert")

class PoolUpdate(BaseFortiadcTask):

    def execute(self, listeners, pool_id):
        LOG.debug("task:PoolUpdate: execute")
        db_pool = self.pool_repo.get(db_apis.get_session(), id = pool_id)
        FadcdeviceDriver(CONF, project_id = db_pool.project_id).pool.update(db_pool)

        for listener in listeners:
            db_listener = self.listener_repo.get(db_apis.get_session(), id = listener[constants.LISTENER_ID])
            FadcdeviceDriver(CONF, project_id = db_listener.project_id).listener.update(db_listener)

    def revert(self, listeners, pool_id, *args, **kwargs):
        LOG.warning("task:PoolUpdate: revert")


class MemberCreate(BaseFortiadcTask):

    def execute(self, member):
        LOG.debug("task:MemberCreate: execute, %s", member)
        #lb_obj = data_models.LoadBalancer.from_dict(loadbalancer)
        db_member = self.member_repo.get(db_apis.get_session(), id = member[constants.MEMBER_ID])
        FadcdeviceDriver(CONF, project_id = db_member.project_id).member.create(db_member)

    def revert(self, member, *args, **kwargs):
        LOG.warning("task:MemberCreate: revert")


class MemberDelete(BaseFortiadcTask):

    def execute(self, member):
        LOG.debug("task:MemberDelete: execute")
        db_member = self.member_repo.get(db_apis.get_session(), id = member[constants.MEMBER_ID])
        FadcdeviceDriver(CONF, project_id = db_member.project_id).member.delete(db_member)

    def revert(self, member, *args, **kwargs):
        LOG.warning("task:MemberDelete: revert")

class MemberDeleteObj(BaseFortiadcTask):

    def execute(self, member):
        LOG.debug("task:MemberDeleteObj: execute")
        FadcdeviceDriver(CONF, project_id = member.project_id).member.delete(member)

    def revert(self, member, *args, **kwargs):
        LOG.warning("task:MemberDeleteObj: revert")

class MemberUpdate(BaseFortiadcTask):

    def execute(self, member):
        LOG.debug("task:MemberUpdate: execute")
        db_member = self.member_repo.get(db_apis.get_session(), id = member[constants.MEMBER_ID])
        FadcdeviceDriver(CONF, project_id = db_member.project_id).member.update(db_member)

    def revert(self, member, *args, **kwargs):
        LOG.warning("task:MemberUpdate: revert")

class HealthMonitorCreate(BaseFortiadcTask):
    def execute(self, health_mon, loadbalancer):
        LOG.debug("task:HealthMonitorCreate:execute, %s", health_mon)
        #lb_obj = data_models.LoadBalancer.from_dict(loadbalancer)
        db_health_monitor = self.health_mon_repo.get(db_apis.get_session(), id = health_mon[constants.HEALTHMONITOR_ID])
        
        FadcdeviceDriver(CONF, project_id = db_health_monitor.project_id).healthmonitor.create(db_health_monitor)
        self.update_status(loadbalancer['loadbalancer_id'])

    def revert(self, health_mon, loadbalancer, *args, **kwargs):
        LOG.warning("task:HealthMonitorCreate: revert")

class HealthMonitorDelete(BaseFortiadcTask):

    def execute(self, health_mon):
        LOG.debug("task:HealthMonitorDelete: execute")
        db_health_monitor = self.health_mon_repo.get(db_apis.get_session(), id = health_mon[constants.HEALTHMONITOR_ID])
        FadcdeviceDriver(CONF, project_id = db_health_mon.project_id).healthmonitor.delete(db_health_mon)

    def revert(self, health_mon, *args, **kwargs):
        LOG.warning("task:HealthMonitorDelete: revert")

class HealthMonitorDeleteObj(BaseFortiadcTask):

    def execute(self, health_mon):
        LOG.debug("task:HealthMonitorDeleteObj: execute")
        FadcdeviceDriver(CONF, project_id = health_mon.project_id).healthmonitor.delete_direct(health_mon)

    def revert(self, health_mon, *args, **kwargs):
        LOG.warning("task:HealthMonitorDelete: revert")

class HealthMonitorUpdate(BaseFortiadcTask):

    def execute(self, health_mon, loadbalancer):
        LOG.debug('task:HealthMonitorUpdate: health_mon is %s', health_mon)
        db_health_monitor = self.health_mon_repo.get(db_apis.get_session(), id = health_mon[constants.HEALTHMONITOR_ID])
        LOG.debug('task:HealthMonitorUpdate: db_health_monitor is %s', db_health_monitor.to_dict())
        FadcdeviceDriver(CONF, project_id = db_health_monitor.project_id).healthmonitor.update(db_health_monitor)
        self.update_status(loadbalancer['loadbalancer_id'])

    def revert(self, health_mon, loadbalancer, *args, **kwargs):
        LOG.warning("task:HealthMonitorUpdate: revert")

