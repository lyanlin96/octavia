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

from fadc_octavia_provider.fortiadc_agent import fadc_api
import requests
from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class Connector(object):
    def __init__(self, host, certificate_verify, ca_file):
        self.host = host
        self.url_prefix = 'https://' + self.host
        self.session = requests.session()
        if certificate_verify:
            self.session.verify = ca_file
        else:
            self.session.verify = False
        self.major = 5
        self.token = ''

    def login(self, name, key):
        url = self.url_prefix + '/api/user/login'
        url_referer = self.url_prefix + '/ui/'
        res = requests.Response()
        payload = {'username':name,'password':key}
        headers = {'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json, text/javascript, */*;',
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Referer': url_referer}
        try:
            res = self.session.post(url, headers=headers, json=payload, timeout=(fadc_api.base.http_connection_timeout, fadc_api.base.http_read_timeout))
            LOG.debug('LOGIN:post end, %s', res.text)

            if False:
                LOG.error('LOGIN fail')
                res.status_code=401
            else:
                #LOG.error("response text %s" %res.text)
                if res.text[0] == '1':
                    LOG.debug('LOGIN succeed %s' % (res))
                elif res.text[0] == '0':
                    # login in failure
                    res.status_code=401
                    LOG.error('LOGIN authentication failure - 401')
                elif res.text[0] == '2':
                    LOG.error('LOGIN blocked - 403')
                    res.status_code=403
                elif res.text.find('Too many bad login attempts or reached max number of logins. Please try again in a few minutes.')!=-1:
                    LOG.error('Too many bad login attempts or reached max number of logins 403')
                    res.status_code=403
            if int(fadc_api.__version__[0]) >= self.major:
                response = res.json()
                if not response:
                    raise requests.ConnectionError("Can't get login token")
                if 'token' in response:
                    self.token = response['token']
                else:
                    raise requests.ConnectionError("Can't get login token")
        except requests.ConnectionError as e:
            LOG.error("login error:%s" %(e))
            #return res

    def logout(self):
        url = self.url_prefix + '/api/user/logout'
        headers = None
        if self.token:
            headers = {'Authorization': 'Bearer ' + self.token}
        res = requests.Response()
        try:
            res = self.session.get(url, headers=headers, timeout=(fadc_api.base.http_connection_timeout, fadc_api.base.http_read_timeout))
            if res.status_code != 200:
                LOG.debug( 'LOGOUT: fail')
            else:
                LOG.debug( ('LOGOUT: succeed %s' % (res)))
        except requests.ConnectionError as e:
            LOG.debug( " %s" %(e))

        #LOG.debug( ("response.text = %s" % (res.text)))
        LOG.debug( 'exit logout')
        return res
    def refresh(self):
        if int(fadc_api.__version__[0]) < self.major:
            return
        url = self.url_prefix + '/api/refresh_token'
        headers = {'Authorization': 'Bearer ' + self.token}
        res = requests.Response()
        try:
            res = self.session.get(url, headers=headers)
            if res.status_code != 200:
                LOG.debug( 'refresh: fail')
            else:
                response = res.json()
                if not response:
                    raise requests.ConnectionError("Can't get refresh token")
                if 'token' in response:
                    self.token = response['token']
                else:
                    raise requests.ConnectionError("Can't get refresh token")
                LOG.info("refresh token %s" %(self.token))
        except requests.ConnectionError as e:
            LOG.debug( "%s" %(e))

        LOG.debug( ("response.text = %s" % (res.text)))
        LOG.debug( 'exit refresh')
    def check_version(self):
        url = self.url_prefix + '/api/platform/version'
        res = requests.Response()
        try:
            res = self.session.get(url, timeout=(fadc_api.base.http_connection_timeout, fadc_api.base.http_read_timeout))
            if res.status_code != 200:
                LOG.error( 'GetVersion: fail')
            else:
                LOG.debug( ('GetVersion: succeed %s' % (res)))
                response = res.json()
                if 'payload' in response:
                    version = response['payload']['version'].replace('-','.')
                    if fadc_api.__version__ != version:
                        if int(version[0]) < self.major:
                            raise Exception('Fortiadc version is under 5.0.0. Upgrade to 5.0.0 is required')
                        LOG.warning('Device driver support Version %s differs from device %s', fadc_api.__version__, version)
                    else:
                        LOG.info("Device version: %s", fadc_api.__version__)

        except requests.ConnectionError as e:
            LOG.debug( "e %s" %(e))

