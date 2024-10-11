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
import sys
import eventlet

eventlet.monkey_patch()

from oslo_config import cfg
from oslo_log import log as oslo_logging
from oslo_service import service
from neutron.common import rpc as n_rpc
from neutron.conf.agent import common as config
from neutron.agent.linux import interface
from neutron.common import config as common_config

from fortinet_openstack_agent import agent_manager as manager
from fortinet_openstack_agent import constants as agent_constants


LOG = oslo_logging.getLogger(__name__)


OPTS = [
    cfg.IntOpt(
        'periodic_interval',
        default=10,
        help=_('Seconds between periodic task runs')
    ),
]

class LbaasAgentService(n_rpc.Service):
    def start(self):
        super(LbaasAgentService, self).start()
        self.tg.add_timer(
            cfg.CONF.periodic_interval,
            self.manager.run_periodic_tasks,
            None,
            None
        )


def main():
    cfg.CONF.register_opts(OPTS)
    cfg.CONF.register_opts(manager.OPTS)

    config.register_interface_driver_opts_helper(cfg.CONF)
    config.register_agent_state_opts_helper(cfg.CONF)
    config.register_root_helper(cfg.CONF)
    if hasattr(config, 'register_interface_opts'):
        config.register_interface_opts(cfg.CONF)
    elif hasattr(interface, 'OPTS'):
        cfg.CONF.register_opts(interface.OPTS)
    else:
        LOG.error('No interface opts to register')

    common_config.init(sys.argv[1:])
    config.setup_logging()

    mgr = manager.LbaasAgentManager(cfg.CONF)
    svc = LbaasAgentService(
        host=cfg.CONF.host,
        topic=agent_constants.TOPIC_LOADBALANCER_AGENT_V2,
        manager=mgr)
    service.launch(cfg.CONF, svc).wait()


if __name__ == '__main__':
    # Handle any missing dependency errors via oslo:
    try:
        Error
    except NameError:
        sys.exc_clear()
    else:
        # We already had an exception, ABORT!
        LOG.exception(str(Error))
        sys.exit(errno.ENOSYS)
    main()
