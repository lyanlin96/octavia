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

import requests
from six import string_types
from oslo_log import log as logging
LOG = logging.getLogger(__name__)


vdom_route = "?vdom="
http_connection_timeout = 3.05
http_read_timeout = 20

class RequestAction(object):
    CREATE = "create"
    DELETE = "delete"
    GETALL = "getall"
    GETONE = "getone"
    UPDATE = "update"
    GETSTATUS = "getstatus"

class HTTPStatus(object):
    # API request succesful.
    OK = 200
    # no content
    NO_CONTENT = 204
    BAD_REQUEST = 400
    # invalid authentication credentials
    UNAUTHORIZED = 401
    # Request is missing CSRF token or administrator is
    # missing access profile permissions.
    FORBIDDEN = 403
    # Unable to find the specified resource.
    NOT_FOUND = 404
    # Specified HTTP method is not allowed for this resource.
    METHOD_NOT_ALLOWED = 405.
    REQUEST_ENTITY_TOO_LARGE = 413
    FAILED_DEPENDENCY = 424
    INTERNAL_SERVER_ERROR = 500


# API class to access FADC REST API
class FADC(object):
    def __init__(self, host, connector, verbose):
        self.host = host
        self.url_prefix = 'https://' + self.host + '/api'
        self.connector = connector
        self.session = connector.session
        self.verbose = verbose
        self.headers = None
        if not self.verbose:
            #level = LOG.logger.getLevelName('WARNING')
            LOG.logger.setLevel(logging.WARNING)
        if connector.token:
            self.headers = {'Authorization': 'Bearer ' + connector.token}

    def get(self, url_postfix, params=None, data=None):
        url = self.url_prefix + url_postfix
        res = requests.Response()
        try:
            res = self.session.get(url, headers=self.headers, params=params, data=data, timeout=(http_connection_timeout, http_read_timeout))
            if res.status_code != 200:
                LOG.debug( 'GET: fail')
            else:
                LOG.debug("res= %s" % (res))
            return self.check_response(res)
        except requests.ConnectionError as e:
            return self.check_response(res)


    def post(self, url_postfix, params=None, data=None):
        url = self.url_prefix + url_postfix
        res = requests.Response()
        try:
            res = self.session.post(url, headers=self.headers, params=params, json=data, timeout=(http_connection_timeout, http_read_timeout))
            #if res.text.find('error') != -1:
            if res.status_code != 200:
                LOG.debug( 'POST: fail')
            else:
                #print("POST:wdai+++%s" %(str(params)))
                #print("POST:wdai:text "+str(res.text))
                LOG.debug( 'POST: res %s cookies %s' % (res, self.session.cookies))
            return self.check_response(res)
        except requests.ConnectionError as e:
            LOG.debug( "e %s" %(e))
            return self.check_response(res)

    def put(self, url_postfix, params=None, data=None):
        url = self.url_prefix + url_postfix
        res = requests.Response()
        try:
            res = self.session.put(url, headers=self.headers, params=params, json=data, timeout=(http_connection_timeout, http_read_timeout))
            if res.status_code != 200:
                LOG.debug( 'PUT: fail')
            else:
                LOG.debug( 'PUT: res %s cookies %s' % (res, self.session.cookies))
            return self.check_response(res)
        except requests.ConnectionError as e:
            LOG.debug( "e %s" %(e))
            return self.check_response(res)

    def _delete(self, url_postfix, params=None, data=None):
        url = self.url_prefix + url_postfix
        res = requests.Response()
        try:
            res = self.session.delete(url, headers=self.headers, params=params, json=data, timeout=(http_connection_timeout, http_read_timeout))
            if res.status_code != 200:
                LOG.debug( 'DELETE: fail')
            else:
                LOG.debug( 'DELETE: res %s cookies %s' % (res, self.session.cookies))
            return self.check_response(res)
        except requests.ConnectionError as e:
            LOG.debug( "e %s" %(e))
            return self.check_response(res)

    def doAction(self, method):
        return {
            RequestAction.CREATE: self.post,
            RequestAction.DELETE: self._delete,
            RequestAction.UPDATE: self.put,
            RequestAction.GETALL: self.get,
            RequestAction.GETONE: self.get,
            RequestAction.GETSTATUS: self.get
        }.get(method)
    def action_handler(self, method, errcodes, obj):
        config = self.mapping(obj) if method in [RequestAction.CREATE, RequestAction.UPDATE] else None
        vdom_name = obj.project_id
        url = self.prefix
        ok = True
        if method in [RequestAction.CREATE, RequestAction.GETALL]:
            url += vdom_route + vdom_name
        #elif method in [RequestAction.DELETE, RequestAction.UPDATE]:
        #    url += "/" + obj.id + vdom_route + vdom_name
        elif method in [RequestAction.DELETE, RequestAction.UPDATE, RequestAction.GETONE, RequestAction.GETSTATUS]:
            url += vdom_route + vdom_name + "&mkey=" + obj.id

        if method == RequestAction.UPDATE:
            old = self.getone(obj)
            if old:
                old.update(config)
                config = old
            else:
                LOG.debug("Get old %s failed", obj.id)
                return not ok
        else:
            if config:
                config.update(self.attrs_set_on_device())
        response = self.doAction(method)(url, None, config)

        ok = self.response_handler(response, errcodes)
        if ok and method in [RequestAction.GETALL, RequestAction.GETONE]:
            return response.json()['payload']

        if ok and method in [RequestAction.GETSTATUS]:
            return response.text
        return ok

    def check_response(self, response):
        if response.status_code==None:
            LOG.debug( 'no response')
            return response
        if self.verbose:
            LOG.debug( '+++++{0} {1}'.format(response.request.method,
                                   response.request.url))

        LOG.debug( ("response.text = %s" % (response.text)))
        # Check response status, content and compare with original request
        if response.status_code == 200:
            # Success code, now check json response
            try:
                # Retrieve json data
                res = response.json()
            except:
                if self.verbose:
                    LOG.debug( 'Fail invalid JSON response')
                    LOG.debug( response.text)
                #return False
                # to workaround fortigate issue with response code ok but the json content is invalide (no content)
                response.status_code=204
                return response

            else:
                # Check if json data is empty
                if not res:
                    if self.verbose:
                        LOG.debug( "JSON data is empty")
                        LOG.debug( response.text)
                    return response

                # Check status
                if 'status' in res:
                    if res['status'] != 'success':
                        if self.verbose:
                            LOG.debug( 'JSON error {0}\n{1}'.format(res['error'], res))
                        return response

                # Check http_status if any
                if 'http_status' in res:
                    if res['http_status'] != 200:
                        if self.verbose:
                            LOG.debug( 'JSON error {0}\n{1}'.format(res['error'], res))
                        return response

                # Check http method
                if 'http_method' in res:
                    if res['http_method'] != response.request.method:
                        if self.verbose:
                            LOG.debug( 'Incorrect METHOD request {0},\
                                  response {1}'.format(response.request.method,
                                                       res['http_method']))
                        return response

                # Check results
                if 'results' in res:
                    #print res['results']
                    if not res['results']:
                        if self.verbose:
                            LOG.debug( 'Results is empty')
                        return response

                if self.verbose:
                    LOG.debug( 'Succeed with status: {0}'.format(response.status_code))
                    if response.request.method != "GET":
                        LOG.debug( 'res %s' %(res))
                # Check License, timeout
                if 'payload' in res:
                    if isinstance (res['payload'], string_types):
                        if 'Invalid VM License' ==  res['payload']:
                            if self.verbose:
                                LOG.error('Invalid VM License')
                            response.status_code = 401
                        if 'Session Timeout' ==  res['payload']:
                            if self.verbose:
                                LOG.error('Session timeout')
                            response.status_code = 401
                # Check vdom

                # Check path

                # Check name

                # Check action

                # All pass
                #return True
                return response
        else:
            try:
                # Retrieve json data
                res = response.json()
            except:
                if self.verbose:
                    LOG.debug( 'Fail with status: {0}'.format(response.status_code))
            else:
                if self.verbose:
                    LOG.debug( 'Fail with status: {0}'.format(response.status_code))
                if 'message' in res:
                    if isinstance (res['message'], string_types):
                        if 'Token is expired' ==  res['message']:
                            LOG.error('%s' %(res['message']))
                    #print response.json()
            finally:
                if self.verbose:
                    LOG.debug( ("response.text = %s" % (response.text)))
                return response

    def response_handler(self, response, errcodes):
        if response.status_code == HTTPStatus.FAILED_DEPENDENCY:
            LOG.error(
                'ERROR: Dependency does not exist. '
                'Will retry add vdom %s.' % self.project_id
            )
            return 0
        elif response.status_code == HTTPStatus.FORBIDDEN:
            LOG.error(
                'ERROR: Adding vdom %s is missing CSRF token or administrator '
                'is missing access profile permissions.' % (self.project_id)
            )
            return 0
        elif response.status_code != HTTPStatus.OK:
            return 0
        else:
            if isinstance(response.json()['payload'], int):
                if (response.json()['payload'] == 0 or response.json()['payload'] in errcodes):
                    return 1
                else:
                    return 0
            else:
                return 1
