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

"""

"""

from fadc_api.healthcheck import HealthCheck
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

monitor_type = {
    "HTTP":"http",
    "HTTPS":"https",
    "PING":"icmp",
    "TCP":"tcp",
    #"TLS-HELLO":"tcpssl"
}


class HealthMonitor(object):

    def __init__(self, fadc_driver):
        self.conf = fadc_driver.conf
        self.hc = HealthCheck(fadc_driver.host, fadc_driver.connector, self.conf.debug_mode)

    def create(self, hm):
        LOG.debug("create healthmonitor")
        self.check_parameter(hm)
        self.hc.create(hm)

    def update(self,old_hm, hm):
        LOG.debug("update healthmonitor")
        self.check_parameter(hm)
        self.hc.update(hm)

    def delete(self, hm):
        LOG.debug("delete healthmonitor")
        self.hc.delete(hm)

    def check_parameter(self, hm):
        if hm.timeout >= hm.delay:
            raise Exception('Timeout must be less than the delay value')
        if hm.type not in monitor_type.keys():
            raise Exception('not support')
        else:
            hm.fadc_type = monitor_type[hm.type]
            if hm.type in ["HTTP", "HTTPS"]:
                if hm.http_method not in ["GET", "HEAD"]:
                    raise Exception('not support')
        hm.fadc_method_type = "http_" + hm.http_method.lower()
        hm.fadc_port = self.conf.fadc_healthcheck_port
