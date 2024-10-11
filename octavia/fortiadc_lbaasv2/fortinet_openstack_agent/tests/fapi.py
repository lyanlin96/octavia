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

import requests


class Connector(object):
    def __init__(self, host):
        self.host = host
        self.url_prefix = 'http://' + self.host
        self.session = requests.session()

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
            res = self.session.post(url, headers=headers, json=payload)
            print('hello')
            #if res.status_code != 200:
            if False:
                # Found some error in the response, consider login failed
                res.status_code=401
            else:
                print res.status_code
                #LOG.error("response text %s" %res.text)
                if res.text[0] == '1':
                    print("login succss")
                elif res.text[0] == '0':
                    # login in failure
                    res.status_code=401
                elif res.text[0] == '2':
                    res.status_code=403
                elif res.text.find('Too many bad login attempts or reached max number of logins. Please try again in a few minutes.')!=-1:
                    res.status_code=403
            return res
        except requests.ConnectionError as e:
            print("exc")
            #return res

    def logout(self):
        url = self.url_prefix + '/api/user/logout'
        res = requests.Response()
        try:
            res = self.session.post(url)
            #if res.text.find('error') != -1:
            if res.status_code != 200:
                print( 'LOGOUT: fail')
            else:
                print( ('LOGOUT: succeed %s' % (res)))
                # Update session's csrftoken
        except requests.ConnectionError as e:
            print( "e %s" %(e))

        print( 'exit logout')
        return res






class listenertest(object):
    def __init__(self):
        self.tenant_id = "root"
        self.id = "10"
        self.protocol = "HTTP"
        self.loadbalancer_id = "190"
        self.protocol_port =80
        self.connection_limit = -1
        self.admin_state_up = True

vdom_route = "?vdom="

class RequestAction(object):
    CREATE = "create"
    DELETE = "delete"
    GETALL = "getall"
    GETONE = "getone"
    UPDATE = "update"

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
    def __init__(self, host, connector, verbose=True):
        self.host = host
        self.url_prefix = 'http://' + self.host + '/api'
        self.connector = connector
        self.session = connector.session
        self.verbose = verbose

    def get(self, url_postfix, params=None, data=None):
        url = self.url_prefix + url_postfix
        res = requests.Response()
        try:
            res = self.session.get(url, params=params, data=data)
            if res.status_code != 200:
                print(res.status_code)
            return self.check_response(res)
        except requests.ConnectionError as e:
            return self.check_response(res)



    def check_response(self, response):
        if response.status_code==None:
            return response

        # Check response status, content and compare with original request
        if response.status_code == 200:
            # Success code, now check json response
            try:
                # Retrieve json data
                res = response.json()
            except:
                #return False
                # to workaround fortigate issue with response code ok but the json content is invalide (no content)
                response.status_code=204
                return response

            else:
                # Check if json data is empty
                if not res:
                    return response

                # Check status
                if 'status' in res:
                    if res['status'] != 'success':
                        return response

                # Check http_status if any
                if 'http_status' in res:
                    if res['http_status'] != 200:
                        return response

                # Check http method
                if 'http_method' in res:
                    if res['http_method'] != response.request.method:
                        return response

                # Check results
                if 'results' in res:
                    #print res['results']
                    if not res['results']:
                        return response

                return response
        else:
            try:
                # Retrieve json data
                res = response.json()
            except:
                pass
            else:
                pass
            finally:
                return response


    def get_all_vs_stats(self,vs):

        vs_stats = {'bytesIn':0,
                    'bytesOut':0,
                    'curConns':0,
                    'totConns':0
                   }
        if True:
            interval = "10"
            ptype = "5"
            #will retrive all history data
            count = "60"
            param = "&range=" + ptype + "&mkey=" + vs.id
            url = "/status_history/openstack" + vdom_route + vs.tenant_id + param
            print(url)
            response = self.get(url)
            if True:
                vs_stats['bytesIn'] = sum(int(e) for e in response.json()['payload']['in_bytes'])
                vs_stats['bytesOut'] = sum (int(e) for e in response.json()['payload']['out_bytes'])
                vs_stats['curConns'] = sum (int(e) for e in response.json()['payload']['current_sessions'])
                vs_stats['totConns'] = sum (int(e) for e in (response.json()['payload']['total_sessions']))
                '''
                if 'Inbound Throughput' in throughput[0].values():
                    for ele in throughput[0]['data']:
                        vs_stats['bytesIn'] += ele['val']*int(interval)/8

                    vs_stats['bytesIn'] = int(vs_stats['bytesIn'])

                if 'Outbound Throughput' in throughput[1].values():
                    for ele in throughput[1]['data']:
                        vs_stats['bytesOut'] += ele['val']*int(interval)/8

                    vs_stats['bytesOut'] += int(vs_stats['bytesOut'])
                '''

            #url = "/fast_statis/sessions_all" + vdom_route + vs.tenant_id + param

            #response = self.get(url)
            '''
            if True:
                connections = response.json()['payload']
                if 'Concurrent Connections' in connections[0].values():
                    for ele in connections[0]['data']:
                        vs_stats['curConns'] += ele['val']

                if 'Connections per Second' in connections[1].values():
                    for ele in connections[1]['data']:
                        vs_stats['totConns'] += ele['val']*int(interval)
                        #vs_stats['totConns'] += ele['val']*int(interval)
                    vs_stats['totConns'] = int(vs_stats['totConns'])
            '''
            print(vs_stats)
import time
if __name__ == "__main__":
    conn = Connector('10.0.100.84')
    conn.login('admin','')
    li = listenertest()
    f = FADC('10.0.100.84', conn)
    while True:
        time.sleep(3)
        f.get_all_vs_stats(li)
