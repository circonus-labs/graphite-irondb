import sys
import itertools
import time
import threading
import copy
import json
import os
import binascii
from typing import Dict
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
try:
    from urlparse import urlparse, urlunparse
except ImportError:
    from urllib.parse import urlparse, urlunparse

import requests
import concurrent.futures
import django
from django.conf import settings

from graphite.intervals import Interval, IntervalSet
from graphite.node import LeafNode, BranchNode
from graphite.logger import log
from graphite.finders.utils import FindQuery
try:
    from graphite.finders.utils import BaseFinder
except ImportError:
    BaseFinder = object
try:
    from graphite.tags.base import BaseTagDB
except ImportError:
    BaseTagDB = object

try:
    import flatcc as irondb_flatbuf
    log.info("IRONdb Using flatcc native Flatbuffer module")
except ImportError:
    import flatbuf as irondb_flatbuf
    log.info("IRONdb Using pure Python Flatbuffer module")
log.info(irondb_flatbuf)


def strip_prefix(path):
    prefix = None
    url = list(urlparse(path))
    path = [s for s in url[2].split('/') if s]
    # '', 'find', <account id>, <prefix?>, <endpoint>, ''?
    if len(path) == 4:
        prefix = path.pop(-2)
    url[2] = '/'.join(path)
    return urlunparse(url), prefix

class URLs(object):
    def __init__(self, hosts, rotate=None):
        len_hosts = len(hosts)
        if rotate and isinstance(rotate, int) and len_hosts > 1:
            r = rotate % len_hosts
            hosts = hosts[r:] + hosts[:r]        
        self.iterator = itertools.cycle(hosts)
        self.hc = len(hosts)

    @property
    def host(self):
        return next(self.iterator)

    @property
    def names(self):
        return '{0}/metrics/find/'.format(self.host)

    @property
    def series(self):
        return '{0}/series/'.format(self.host)

    @property
    def series_multi(self):
        return '{0}/series_multi/'.format(self.host)

    @property
    def tags(self):
        return '{0}/tags/find/'.format(self.host)

    @property
    def tag_cats(self):
        return strip_prefix('{0}/tag_cats/'.format(self.host).replace('/graphite/', '/find/', 1))

    @property
    def tag_vals(self):
        return strip_prefix('{0}/tag_vals/'.format(self.host).replace('/graphite/', '/find/', 1))

    @property
    def host_count(self):
        return self.hc

urls = None
urllength = 4096

class IRONdbLocalSettings(object):
    _inst = None

    @classmethod
    def load(cls, obj):
        inst = cls._inst
        if inst is None:
            cls._inst = inst = cls()
        for attr in dir(inst):
            if not attr.startswith('__'):
                setattr(obj, attr, getattr(inst, attr))

    def __init__(self):
        global urls
        try:
            _rotate_urls = getattr(settings, 'IRONDB_URLS_ROTATE')
        except AttributeError:
            _rotate_urls = True        
        if urls is None:
            urls = getattr(settings, 'IRONDB_URLS')
            if not urls:
                urls = [settings.IRONDB_URL]
            if _rotate_urls:
                urls = URLs(urls, rotate=os.getpid())
            else:
                urls = URLs(urls)
        try:
            bs = getattr(settings, 'IRONDB_BATCH_SIZE')
            if bs:
                self.batch_size = int(bs)
        except AttributeError:
            self.batch_size = 250
        try:
            to = getattr(settings, 'IRONDB_TIMEOUT_MS')
            if to:
                self.timeout = int(to)
        except AttributeError:
            self.timeout = 10000
        try:
            cto = getattr(settings, 'IRONDB_CONNECTION_TIMEOUT_MS')
            if cto:
                self.connection_timeout = int(cto)
        except AttributeError:
            self.connection_timeout = 3005
        try:
            token = getattr(settings, 'CIRCONUS_TOKEN')
            if token:
                self.headers = {}
                self.headers['X-Circonus-Auth-Token'] = token
                self.headers['X-Circonus-App-Name'] = 'graphite-web'
        except AttributeError:
            self.headers = {}
        self.headers['X-Snowth-Timeout'] = str(self.timeout) + 'ms'
        try:
            self.activity_tracking = getattr(settings, 'IRONDB_USE_ACTIVITY_TRACKING')
        except AttributeError:
            self.activity_tracking = True
        try:
            self.database_rollups = getattr(settings, 'IRONDB_USE_DATABASE_ROLLUPS')
        except AttributeError:
            self.database_rollups = True
        try:
            self.rollup_window = getattr(settings, 'IRONDB_ROLLUP_WINDOW')
        except AttributeError:
            self.rollup_window = (60 * 60 * 24 * 7 * 4) # one month
        try:
            mr = getattr(settings, 'IRONDB_MAX_RETRIES')
            if mr:
                self.max_retries = int(mr)
        except AttributeError:
            self.max_retries = urls.host_count
        try:
            self.query_log_enabled = getattr(settings, 'IRONDB_QUERY_LOG')
        except AttributeError:
            self.query_log_enabled = False
        try:
            self.zipkin_enabled = getattr(settings, 'IRONDB_ZIPKIN_ENABLED')
        except AttributeError:
            self.zipkin_enabled = False
            self.zipkin_event_trace_level = 0
        try:
            tl = getattr(settings, 'IRONDB_ZIPKIN_EVENT_TRACE_LEVEL')
            if tl:
                self.zipkin_event_trace_level = int(tl)
                if self.zipkin_event_trace_level < 0:
                    # Somebody tried to get cute, just disable it
                    log.info("Can't set IRONDB_ZIPKIN_EVENT_TRACE_LEVEL below zero, setting to zero\n")
                    self.zipkin_event_trace_level = 0
                elif self.zipkin_event_trace_level > 2:
                    # We only support level 1 for now... may add support
                    # for higher levels later
                    log.info("Can't set IRONDB_ZIPKIN_EVENT_TRACE_LEVEL above two... setting to two\n")
                    self.zipkin_event_trace_level = 2
            else:
                self.zipkin_event_trace_level = 0
        except AttributeError:
            self.zipkin_event_trace_level = 0


class HTTPClientSeq(object):
    __slots__ = ('headers', 'params', 'fetched', 'data_type', 'result', 'zipkin_level', 'timeout', 'logger', 'caller')

    def __init__(self, headers=None, params=None, zipkin_level=0, timeout=(0,0), logger=None, caller=''):
        if headers == None:
            headers = {}
        self.headers = headers
        if params == None:
            params = {}
        self.params = params
        self.zipkin_level = zipkin_level
        self.timeout = timeout
        self.fetched = False
        self.data_type = 'json'
        self.result = None
        self.logger = logger
        self.caller = caller
                                
    def request(self, method='GET', urls=None, start_time=0, end_time=0):
        query_type = "rollup data" if self.params.get("database_rollups") else "raw data"
        if self.headers['Accept'] == 'application/x-flatbuffer-metric-find-result-list':
            query_type = "names"
        for url in urls:
            if self.zipkin_level > 0:
                traceheader = binascii.hexlify(os.urandom(8))
                self.headers['X-B3-TraceId'] = traceheader
                self.headers['X-B3-SpanId'] = traceheader
                if self.zipkin_level == 1:
                    self.headers['X-Mtev-Trace-Event'] = '1'
                elif self.zipkin_level == 2:
                    self.headers['X-Mtev-Trace-Event'] = '2'
            try:
                query_start = time.gmtime()
                d = requests.request(method, url, params=self.params, json=self.params, headers=self.headers, timeout=self.timeout)
                d.raise_for_status()
                if d.status_code == 200:
                    self.fetched = True
                    if d.headers['content-type'] == 'application/x-flatbuffer-metric-get-result-list':
                        data_type = "flatbuffer"
                        self.result = irondb_flatbuf.metric_get_results(d.content)
                    elif d.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                        data_type = "flatbuffer"
                        self.result = irondb_flatbuf.metric_find_results(d.content)
                    else:
                        data_type = "json"
                        self.result = d.json()
                if 'data' in query_type:
                    req = json.dumps(self.params)
                    result_count = len(self.result["series"]) if self.result else -1
                else:
                    req = self.params["query"]
                    result_count = len(self.result) if self.result else -1
                if self.logger:
                    self.logger.query_log(url, query_start, d.elapsed, result_count, req, query_type, data_type, start_time, end_time)
                break
            except requests.exceptions.ConnectionError as ex:
                # on down nodes, retry on another up to "tries" times
                log.exception("%s ConnectionError %s" % (self.caller, ex))
            except requests.exceptions.ConnectTimeout as ex:
                # on down nodes, retry on another up to "tries" times
                log.exception("%s ConnectTimeout %s" % (self.caller, ex))
            except irondb_flatbuf.FlatBufferError as ex:
                # flatbuffer error, try again
                log.exception("%s FlatBufferError %s" % (self.caller, ex))
            except JSONDecodeError as ex:
                # json error, try again
                log.exception("%s JSONDecodeError %s" %(self.caller,  ex))
            except requests.exceptions.ReadTimeout as ex:
                # read timeouts are failures, stop immediately
                log.exception("%s ReadTimeout %s" % (self.caller, ex))
                break
            except requests.exceptions.HTTPError as ex:
                # http status code errors are failures, stop immediately
                log.exception("%s HTTPError %s %s" % (self.caller, ex, d.content))
                break
        if self.fetched:
            return self.result
        else:
            return {}


class HTTPClientFutures(object):
    __slots__ = ('workers', 'headers', 'params', 'fetched', 'data_type', 'result', 'zipkin_level', 'timeout', 'logger', 'caller')

    def __init__(self, headers=None, params=None, zipkin_level=0, timeout=(0,0), logger=None, caller='', workers=10):
        if headers == None:
            headers = {}
        self.headers = headers
        if params == None:
            params = {}
        self.params = params
        self.zipkin_level = zipkin_level
        self.timeout = timeout
        self.fetched = False
        self.data_type = 'json'
        self.result = None
        self.logger = logger
        self.caller = caller
        self.workers = workers
                                
    def request(self, method='GET', urls=None, start_time=0, end_time=0):

        def _load_url(method, url, params, headers, timeout, zipkin_level, logger):
            result = None
            query_type = "rollup data" if params.get("database_rollups") else "raw data"
            if headers['Accept'] == 'application/x-flatbuffer-metric-find-result-list':
                query_type = "names"
            if zipkin_level > 0:
                traceheader = binascii.hexlify(os.urandom(8))
                headers['X-B3-TraceId'] = traceheader
                headers['X-B3-SpanId'] = traceheader
                if zipkin_level == 1:
                    headers['X-Mtev-Trace-Event'] = '1'
                elif zipkin_level == 2:
                    headers['X-Mtev-Trace-Event'] = '2'
            query_start = time.gmtime()    
            res = requests.request(method, url, params=params, json=params, headers=headers, timeout=timeout)
            res.raise_for_status()
            if res.status_code == 200:
                if res.headers['content-type'] == 'application/x-flatbuffer-metric-get-result-list':
                    data_type = "flatbuffer"
                    result = irondb_flatbuf.metric_get_results(res.content)
                elif res.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                    data_type = "flatbuffer"
                    result = irondb_flatbuf.metric_find_results(res.content)
                else:
                    data_type = "json"
                    result = res.json()
                if 'data' in query_type:
                    req = json.dumps(params)
                    result_count = len(result["series"]) if result else -1
                else:
                    req = params["query"]
                    result_count = len(result) if result else -1
                if logger:
                    logger.query_log(url, query_start, res.elapsed, result_count, req, query_type, data_type, start_time, end_time)
            return result

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.workers)
        _fetched = False
        result = None
        futures = []
        for url in urls:
            futures.append(
                executor.submit(_load_url, method, url, self.params, self.headers, self.timeout, self.zipkin_level, self.logger)
            )
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if isinstance(result, list) and len(result) > 0:
                    _fetched = True
                    break
                elif isinstance(result, dict) and len(result.get("series")) > 0:
                    _fetched = True
                    break
            except concurrent.futures.CancelledError as ex:
                pass
            except requests.exceptions.ConnectionError as ex:
                log.exception("%s ConnectionError %s" % (self.caller, ex))
            except requests.exceptions.ConnectTimeout as ex:
                log.exception("%s ConnectTimeout %s" % (self.caller, ex))
            except irondb_flatbuf.FlatBufferError as ex:
                log.exception("%s FlatBufferError %s" % (self.caller, ex))
            except JSONDecodeError as ex:
                log.exception("%s JSONDecodeError %s" %(self.caller,  ex))
            except requests.exceptions.ReadTimeout as ex:
                log.exception("%s ReadTimeout %s" % (self.caller, ex))
            except requests.exceptions.HTTPError as ex:
                log.exception("%s HTTPError %s %s" % (self.caller, ex, d.content))
        if _fetched:
            return result
        else:
            return None


class IRONdbMeasurementFetcher(object):
    __slots__ = ('leaves','lock', 'fetched', 'results', 'headers', 'database_rollups', 'rollup_window', 'timeout', 'connection_timeout', 'retries',
                 'zipkin_enabled', 'zipkin_event_trace_level')

    def __init__(self, headers, timeout, connection_timeout, db_rollups, rollup_window, retries, zipkin_enabled, zipkin_event_trace_level):
        self.leaves = list()
        self.lock = threading.Lock()
        self.fetched = False
        self.results = {}
        self.headers = {}
        self.timeout = timeout
        self.connection_timeout = connection_timeout
        self.database_rollups = db_rollups
        self.rollup_window = rollup_window
        self.retries = retries
        self.zipkin_enabled = zipkin_enabled
        self.zipkin_event_trace_level = zipkin_event_trace_level
        if headers:
            self.headers = headers

    def add_leaf(self, leaf_name, leaf_data):
        self.leaves.append({'leaf_name': leaf_name, 'leaf_data': leaf_data})

    def fetch(self, query_log, start_time, end_time):
        if (len(self.leaves) == 0):
            # nothing to fetch, we're done
            return
        if (self.fetched == False):
            self.lock.acquire()
            # recheck in case we were waiting
            if (self.fetched == False):
                params = {}
                params['names'] = self.leaves
                params['start'] = start_time
                params['end'] = end_time
                now = int(time.time())
                if start_time < (now - self.rollup_window):
                    params['database_rollups'] = True
                else:
                    params['database_rollups'] = self.database_rollups
                tries = self.retries
                url_list = (urls.series_multi for _ in range(0, max(urls.host_count, tries)))
                send_headers = copy.deepcopy(self.headers)
                q = HTTPClientFutures(headers=send_headers, params=params, 
                    zipkin_level=self.zipkin_event_trace_level, 
                    timeout=((self.connection_timeout / 1000), (self.timeout / 1000)),
                    logger=query_log, caller='IRONdbMeasurementFetcher.fetch',
                    workers=urls.host_count)
                #q = HTTPClientSeq(headers=send_headers, params=params, 
                #    zipkin_level=self.zipkin_event_trace_level, 
                #    timeout=((self.connection_timeout / 1000), (self.timeout / 1000)),
                #    logger=query_log, caller='IRONdbMeasurementFetcher.fetch')                
                self.fetched = False
                result = q.request('POST', url_list, start_time, end_time)
                if result:
                    self.results = result
                    self.fetched = True

            if settings.DEBUG:
                log.debug("IRONdbMeasurementFetcher.fetch results: %s" % json.dumps(self.results))
            self.lock.release()
            
    def is_error(self):
        return self.fetched == False or self.results == None or 'error' in self.results or len(self.results['series']) == 0

    def series(self, name):
        if self.is_error():
            return

        time_info = self.results['from'], self.results['to'], self.results['step']
        if len(self.results['series'].get(name, [])) == 0:
            return time_info, [None] * ((self.results['to'] - self.results['from']) / self.results['step'])

        return time_info, self.results['series'].get(name, [])

class IRONdbReader(object):
    __slots__ = ('name', 'fetcher',)

    def __init__(self, name, fetcher):
        self.name = name
        self.fetcher = fetcher

    def fetch(self, start_time, end_time):
        self.fetcher.fetch(start_time, end_time)
        return self.fetcher.series(self.name)

    def get_intervals(self):
        # all time
        return IntervalSet([Interval(0, int(time.time()))])


class IRONdbFinder(BaseFinder):
    __slots__ = ('disabled', 'batch_size', 'database_rollups', 'timeout',
                 'connection_timeout', 'headers', 'disabled', 'max_retries',
                 'query_log_enabled', 'zipkin_enabled',
                 'zipkin_event_trace_level')

    def __init__(self, config=None):
        global urls
        if config is not None:
            self.batch_size = 250
            self.database_rollups = True
            self.timeout = 10000
            self.connection_timeout = 3005
            self.headers = {}
            self.disabled = False
            self.query_log_enabled = False
            self.zipkin_enabled = False
            self.zipkin_event_trace_level = 0
            if 'urls' in config['irondb']:
                urls = config['irondb']['urls']
            else:
                urls = [config['irondb']['url'].strip('/')]
            if 'batch_size' in config['irondb']:
                self.batch_size = config['irondb']['batch_size']
            urls = URLs(urls)
            self.max_retries = urls.host_count
        else:
            IRONdbLocalSettings.load(self)

    def query_log(self, node, start, elapsed, result_count, query, query_type, data_format, data_start, data_end):
        if self.query_log_enabled == False:
            return

        qs = time.strftime("%Y-%m-%d %H:%M:%S", start)
        e = str(elapsed)

        log.info('******* IRONdb query -- node: %s, start: %s, result_count: %d, type: %s, format: %s, elapsed: %s\n\n  [%s, %s] "%s"\n'
                 % (node, qs, result_count, query_type, data_format, e, data_start, data_end, query))

    def newfetcher(self, fset, headers):
        fetcher = IRONdbMeasurementFetcher(headers, self.timeout, self.connection_timeout, self.database_rollups, self.rollup_window, self.max_retries,
                                           self.zipkin_enabled, self.zipkin_event_trace_level)
        fset.append(fetcher)
        return fetcher

    def dispatchfetches(self, fset, start_time, end_time):
        for fetcher in fset:
            fetcher.fetch(self, start_time, end_time)

    def fetch(self, patterns, start_time, end_time, now=None, requestContext=None):
        log.debug("IRONdbFinder.fetch called")
        all_names = {}
        for pattern in patterns:
            log.debug("IRONdbFinder.fetch pattern: %s" % pattern)
            names = {}
            tries = self.max_retries
            name_headers = copy.deepcopy(self.headers)
            name_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
            name_params = {'query': pattern}
            if self.activity_tracking:
                name_params['activity_start_secs'] = start_time
                name_params['activity_end_secs'] = end_time
            url_list = (urls.names for _ in range(0, max(urls.host_count, tries)))
            r = HTTPClientFutures(headers=name_headers, params=name_params, 
                zipkin_level=self.zipkin_event_trace_level, 
                timeout=((self.connection_timeout / 1000), (self.timeout / 1000)),
                logger=self, caller='IRONdbFinder.fetch',
                workers=urls.host_count)
            #r = HTTPClientSeq(headers=name_headers, params=name_params, 
            #    zipkin_level=self.zipkin_event_trace_level, 
            #    timeout=((self.connection_timeout / 1000), (self.timeout / 1000)),
            #    logger=self, caller='IRONdbFinder.fetch')                
            result = r.request('GET', url_list, start_time, end_time)
            if result:
                all_names[pattern] = result
            else:
                all_names[pattern] = []

        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        in_this_batch = 0
        fset = []
        fetcher = self.newfetcher(fset, measurement_headers)
        for pattern, names in all_names.items():
            for name in names:
                if 'leaf' in name and 'leaf_data' in name:
                    if self.batch_size == 0 or in_this_batch >= self.batch_size:
                        in_this_batch = 0
                        fetcher = self.newfetcher(fset, measurement_headers)
                    fetcher.add_leaf(name['name'], name['leaf_data'])
                    name['fetcher'] = fetcher
                    in_this_batch += 1

        self.dispatchfetches(fset, start_time, end_time)

        results = []
        first_correction = False
        for pattern, names in all_names.items():
            for name in names:
                fetcher = fset[0]
                if 'fetcher' in name:
                    fetcher = name['fetcher']
                res = fetcher.series(name['name'])
                if res is None:
                    continue

                time_info, values = res

                # At least one series needs to have the right start time
                # And to not be complete jerks we cull leading nulls, so on
                # data fetches where everything has leading nulls, the start
                # time in the graph can slide forward.  We need one anchor,
                # it will be whatever series we see first.
                if not first_correction:
                    prepend = []
                    # time_info is immutable, recreate it so we can muck with it
                    time_info = [ time_info[0], time_info[1], time_info[2] ]
                    while time_info[0] > start_time:
                       time_info[0] -= time_info[2]
                       prepend.append(None)
                    if len(prepend) > 0:
                       values = prepend + values
                    first_correction = True
                results.append({
                    'pathExpression': pattern,
                    'path' : name['name'],
                    'name' : name['name'],
                    'time_info' : time_info,
                    'values': values
                })
        return results



    #future work
    def auto_complete_tags(self, exprs, tagPrefix=None, limit=None, requestContext=None):
        return []

    #future work
    def auto_complete_values(self, exprs, tag, valuePrefix=None, limit=None, requestContext=None):
        return []

    # backwards compatible interface for older graphite-web installs
    def find_nodes(self, query):
        log.debug("IRONdbFinder.find_nodes, query: %s, max_retries: %d" % (query.pattern, self.max_retries))
        metrics_expand = False
        if query.pattern.endswith('.**'):
            query.pattern = query.pattern[:-1]
            metrics_expand = True
        names = {}
        tries = self.max_retries
        name_headers = copy.deepcopy(self.headers)
        name_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
        url_list = (urls.names for _ in range(0, max(urls.host_count, tries)))
        r = HTTPClientFutures(headers=name_headers, params={'query': query.pattern}, 
            zipkin_level=self.zipkin_event_trace_level, 
            timeout=((self.connection_timeout / 1000), (self.timeout / 1000)),
            logger=None, caller='IRONdbFinder.find_nodes',
            workers=urls.host_count)
        #r = HTTPClientSeq(headers=name_headers, params={'query': query.pattern}, 
        #    zipkin_level=self.zipkin_event_trace_level, 
        #    timeout=((self.connection_timeout / 1000), (self.timeout / 1000)),
        #    logger=None, caller='IRONdbFinder.find_nodes')                
        names = r.request('GET', url_list, start_time=0, end_time=0)
        if settings.DEBUG:
            log.debug("IRONdbFinder.find_nodes, result: %s" % json.dumps(names))

        # for each set of self.batch_size leafnodes, execute an IRONdbMeasurementFetcher
        # so we can do these in batches.
        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        fetcher = IRONdbMeasurementFetcher(measurement_headers, self.timeout, self.connection_timeout, self.database_rollups, self.rollup_window, self.max_retries,
                                           self.zipkin_enabled, self.zipkin_event_trace_level)

        for name in names:
            if 'leaf' in name and 'leaf_data' in name:
                fetcher.add_leaf(name['name'], name['leaf_data'])
                reader = IRONdbReader(name['name'], fetcher)
                yield LeafNode(name['name'], reader)
            else:
                yield BranchNode(name['name'])
                if metrics_expand:
                    query = FindQuery(name['name'] + '.**', None, None)
                    for node in self.find_nodes(query):
                        yield node


class IRONdbTagFetcher(BaseTagDB):

    def __init__(self, settings, *args, **kwargs):
        super(IRONdbTagFetcher, self).__init__(settings, *args, **kwargs)
        IRONdbLocalSettings.load(self)

    def _request(self, url, query, flatbuffers=False):
        tag_headers = copy.deepcopy(self.headers)
        if flatbuffers:
            tag_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
        if not isinstance(query, dict):
            query = {'query': query}
        source = ""
        if settings.DEBUG:
            source = sys._getframe().f_back.f_code.co_name
        tries = self.max_retries
        for i in range(0, max(urls.host_count, tries)):
            try:
                if self.zipkin_enabled == True:
                    traceheader = binascii.hexlify(os.urandom(8))
                    tag_headers['X-B3-TraceId'] = traceheader
                    tag_headers['X-B3-SpanId'] = traceheader
                    if self.zipkin_event_trace_level == 1:
                        tag_headers['X-Mtev-Trace-Event'] = '1'
                    elif self.zipkin_event_trace_level == 2:
                        tag_headers['X-Mtev-Trace-Event'] = '2'
                r = requests.get(url, params=query, headers=tag_headers,
                                     timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
                r.raise_for_status()
                if flatbuffers:
                    r = irondb_flatbuf.metric_find_results(r.content)
                else:
                    r = r.json()
                if settings.DEBUG:
                    log.debug("IRONdbTagFetcher.%s, result: %s" % (source, json.dumps(r)))
                return r
            except requests.exceptions.ConnectionError as ex:
                # on down nodes, try again on another node until "tries"
                log.exception("IRONdbTagFetcher.%s ConnectionError %s" % (source, ex))
            except requests.exceptions.ConnectTimeout as ex:
                # on down nodes, try again on another node until "tries"
                log.exception("IRONdbTagFetcher.%s ConnectTimeout %s" % (source, ex))
            except irondb_flatbuf.FlatBufferError as ex:
                # flatbuffer error, try again
                log.exception("IRONdbTagFetcher.%s FlatBufferError %s" % (source, ex))
            except JSONDecodeError as ex:
                # json error, try again
                log.exception("IRONdbTagFetcher.%s JSONDecodeError %s" % (source, ex))
            except requests.exceptions.ReadTimeout as ex:
                # up node that simply timed out is a failure
                log.exception("IRONdbTagFetcher.%s ReadTimeout %s" % (source, ex))
                break
            except requests.exceptions.HTTPError as ex:
                # http status code errors are failures, stop immediately
                log.exception("IRONdbTagFetcher.%s HTTPError %s %s" % (source, ex, r.content))
                break
        return ()

    def _find_series(self, tags, requestContext=None):
        query = ','.join(tags)
        tag_series = self._request(urls.tags, query, True)
        return [series['name'] for series in tag_series]

    def list_tags(self, tagFilter=None, limit=None, requestContext=None):
        query = {'query': 'and(*:*)'}
        url, prefix = urls.tag_cats
        if prefix:
            query['prefix'] = prefix
        tag_cats = self._request(url, query)
        return [{'tag': tag} for tag in tag_cats]

    def get_tag(self, tag, valueFilter=None, limit=None, requestContext=None):
        query = {'query': 'and(*:*)', 'category': tag}
        url, prefix = urls.tag_vals
        if prefix:
            query['prefix'] = prefix
        tag_vals = self._request(url, query)
        if not tag_vals:
            return None
        res = []
        for val in tag_vals:
            tag_series = self._request(urls.tags, '%s=%s' % (tag, val), True)
            if not tag_series:
                return None
            tag_count = len(tag_series)
            res.append({'value': val, 'count': tag_count})
        return {'tag': tag, 'values': res}

    # HttpTagDB
    def get_series(self, path, requestContext=None):
        parsed = self.parse(path)

        seriesList = self.find_series(
            [('%s=%s' % (tag, parsed.tags[tag])) for tag in parsed.tags],
            requestContext=requestContext,
        )

        if parsed.path in seriesList:
            return parsed

    # HttpTagDB
    def list_values(self, tag, valueFilter=None, limit=None, requestContext=None):
        tagInfo = self.get_tag(tag, valueFilter=valueFilter, limit=limit, requestContext=requestContext)
        if not tagInfo:
            return []

        return tagInfo['values']

    # DummyTagDB
    def tag_series(self, series, requestContext=None):
        raise NotImplementedError('Tagging not implemented with IRONdbTagFetcher')

    # DummyTagDB
    def del_series(self, series, requestContext=None):
        return True

IronDBFinder = IRONdbFinder
IronDBTagFetcher = IRONdbTagFetcher
