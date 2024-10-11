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

import sys

import json
import cotyledon
from cotyledon import oslo_config_glue
from oslo_config import cfg
from oslo_reports import guru_meditation_report as gmr
from oslo_log import log as logging

from octavia.common import service as octavia_service
from fadc_octavia_provider.fortiadc_agent import consumer as consumer_v2
from fadc_octavia_provider.fortiadc_agent import monitor_service
from fadc_octavia_provider.fortiadc_agent import update_service
from fadc_octavia_provider.fortiadc_agent import stats_service
from octavia import version

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

OPTS = [
    cfg.StrOpt(
        'fadc_FQDN',
        default="172.24.4.24",
        help='FQDN or IP address of FortiADC device'
    ),
    cfg.StrOpt(
        'fadc_username', default='admin',
        help='User with privilege to access the Fortiadc device'
    ),
    cfg.StrOpt(
        'fadc_password', default='a', secret=True,
        help='User password access the Fortiadc device'
    ),
    cfg.ListOpt(
        'fadc_vdom_network_mapping', default=['port2'],
        help='Map network to vdom interfaces'
    ),
    cfg.StrOpt(
        'fadc_vs_dev_intf', default='port2',
        help='Virtual server outgoing interface'
    ),
    cfg.StrOpt(
        'fadc_vs_persistency', default='',
        help='Virtual server persistency'
    ),
    cfg.StrOpt(
        'fadc_vs_packet_forward_method', default='',
        help='Virtual server packet forward method'
    ),
    cfg.StrOpt(
        'fadc_healthcheck_port', default='80',
        help='Health Check monitor port'
    ),
    cfg.StrOpt(
        'fadc_get_stats_interval', default='2',
        help='Set stats interval. 1hr/6hr/1day/1wk/1m/1y'
    ),
    cfg.BoolOpt(
        'debug_mode', default=True,
        help='Enable debug log message on device driver'
    ),
    cfg.DictOpt(
        'fadc_vdom_network_allowAccess', default={'port2':'http ping telnet'}, secret=True,
        #'fadc_vdom_network_allowAccess', default={'port2':'http ping telnet','port3':'http ping telnet'}, secret=True,
        help='Virtual server packet forward method'
    ),
    cfg.DictOpt(
        'fadc_vdom_network_ip', default={'port2':'10.20.2.206/24'}, secret=True,
        #'fadc_vdom_network_ip', default={'port2':'10.20.2.206/24','port3':'10.20.3.41/24'}, secret=True,
        help='port main ip address'
    ),
    cfg.StrOpt(
        'fadc_vdom_default_gw', default='10.20.2.1',
        help='Vdom default gateway'
    ),
    cfg.ListOpt(
        'fadc_vs_nat_pool', default=[],
        #'fadc_vs_nat_pool', default=['10.20.3.200','10.20.3.210'],
        help='FullNAT pool range '
    ),
    cfg.StrOpt(
        'fadc_vs_nat_intf', default='port2',
        help='FullNAT pool interface'
    ),
    cfg.StrOpt(
        'fadc_bind_vip_port_id', default='d9d94803-f6e4-47d9-ba8c-826d606ad36e',
        help='The binding vip port id'
    ),
    cfg.StrOpt(
        'fadc_devices', default='',
        help='fortiadc devices'
    )
]

def init_device_conf(json_devices):
    dict_projects = {}
    for device in json_devices:
        if 'projects' in device:
            for project in device['projects']:
                new_project = {}
                #new_project['vdom'] = project['vdom']
                if 'fadc_FQDN' in device: 
                    new_project['fadc_FQDN'] = device['fadc_FQDN']

                if 'fadc_username' in device: 
                    new_project['fadc_username'] = device['fadc_username']
                else:
                    new_project['fadc_username'] = 'admin' 

                if 'fadc_password' in device: 
                    new_project['fadc_password'] = device['fadc_password']
                else:
                    new_project['fadc_password'] = '' 

                if 'fadc_vdom_network_mapping' in device: 
                    new_project['fadc_vdom_network_mapping'] = device['fadc_vdom_network_mapping']
                else:
                    new_project['fadc_vdom_network_mapping'] = ['port5']

                if 'fadc_bind_vip_port_id' in device: 
                    new_project['fadc_bind_vip_port_id'] = device['fadc_bind_vip_port_id']
                else:
                    raise Exception('fadc_bind_vip_port_id cannot be NULL')

                if 'fadc_vdom_network_allowAccess' in device: 
                    new_project['fadc_vdom_network_allowAccess'] = device['fadc_vdom_network_allowAccess']
                else:
                    new_project['fadc_vdom_network_allowAccess'] = {'port5':'http https ping telnet'} 

                if 'fadc_vdom_network_ip' in device: 
                    new_project['fadc_vdom_network_ip'] = device['fadc_vdom_network_ip']
                else:
                    new_project['fadc_vdom_network_ip'] = {'port5':'172.24.4.129/24'} 

                if 'fadc_vdom_default_gw' in device: 
                    new_project['fadc_vdom_default_gw'] = device['fadc_vdom_default_gw']
                else:
                    new_project['fadc_vdom_default_gw'] = '172.24.4.1' 

                if 'fadc_vs_dev_intf' in device: 
                    new_project['fadc_vs_dev_intf'] = device['fadc_vs_dev_intf']
                else:
                    new_project['fadc_vs_dev_intf'] = 'port5' 

                if 'fadc_vs_packet_forward_method' in device: 
                    new_project['fadc_vs_packet_forward_method'] = device['fadc_vs_packet_forward_method']
                else:
                    new_project['fadc_vs_packet_forward_method'] = '' 

                if 'fadc_vs_nat_pool' in device: 
                    new_project['fadc_vs_nat_pool'] = device['fadc_vs_nat_pool']
                else:
                    new_project['fadc_vs_nat_pool'] = [] 

                if 'fadc_vs_nat_intf' in device: 
                    new_project['fadc_vs_nat_intf'] = device['fadc_vs_nat_intf']
                else:
                    new_project['fadc_vs_nat_intf'] = 'port5' 

                if 'fadc_vs_persistency' in device: 
                    new_project['fadc_vs_persistency'] = device['fadc_vs_persistency']
                else:
                    new_project['fadc_vs_persistency'] = '' 

                if 'fadc_get_stats_interval' in device: 
                    new_project['fadc_get_stats_interval'] = device['fadc_get_stats_interval']
                else:
                    new_project['fadc_get_stats_interval'] = '' 

                if 'fadc_healthcheck_port' in device: 
                    new_project['fadc_healthcheck_port'] = device['fadc_healthcheck_port']
                else:
                    new_project['fadc_healthcheck_port'] = 80

                if 'certificate_verify' in device: 
                    new_project['certificate_verify'] = device['certificate_verify']
                else:
                    new_project['certificate_verify'] = False

                if 'ca_file' in device: 
                    new_project['ca_file'] = device['ca_file']
                else:
                    new_project['ca_file'] = ''

                #dict_projects[project['project_id']] = new_project
                dict_projects[project] = new_project

    CONF.d_projects = dict_projects

def main():
    octavia_service.prepare_service(sys.argv)
    CONF.register_opts(OPTS)
    json_devices = json.loads(CONF.fadc_devices)
    CONF.j_devices = json_devices
    init_device_conf(json_devices)

    gmr.TextGuruMeditation.setup_autorun(version)

    sm = cotyledon.ServiceManager()
    sm.add(monitor_service.MonitorService, workers=1,
           args=(CONF,))
    #sm.add(update_service.UpdateService, workers=1,
    #       args=(CONF,))
    sm.add(stats_service.StatsService, workers=1,
           args=(CONF,))
    sm.add(consumer_v2.ConsumerService,
           workers=CONF.controller_worker.workers, args=(CONF,))
    oslo_config_glue.setup(sm, CONF, reload_method="mutate")
    sm.run()


if __name__ == "__main__":
    main()
