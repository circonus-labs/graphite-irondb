import sys
import itertools
import time
import threading
import copy
import json
import os
import binascii
import re

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
try:
    from urlparse import urlparse, urlunparse
except ImportError:
    from urllib.parse import urlparse, urlunparse

from collections import OrderedDict

import requests
import socket
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

def retrieve_gas(url, connection_timeout, timeout):
    """
    Input:  url string
            connection_timeout, timeout - float ms
    Output: parsed result or OrderedDict()

    Retrieves graphite_adjust_step.json file
    and returns it in parsed form as ordered dict,
    or return empty dict if broken or non-retrievable
    """
    gas = OrderedDict()
    if not url.startswith('http'):
        # relative url
        global urls
        if url.startswith('/'):
            irondb_url_parsed = list(urlparse(urls.host))
            url = '{0}://{1}{2}'.format(irondb_url_parsed[0], irondb_url_parsed[1], url)
        else:
            url = '{0}{1}'.format(urls.host, url)
    try:
        # retrieve graphite_adjust_step.json file
        r = requests.get(url, params={}, headers={},
                timeout=((connection_timeout / 1000.0), (timeout / 1000.0)))
        r.raise_for_status()
        if r.headers['content-type'] == 'application/json':
            for line in r.json():
                rx = re.compile(line['re'])
                gas[rx] = line['step']
    except (requests.exceptions.RequestException, re.error, AttributeError) as ex:
        pass
    return gas

def find_minimal_interval_in_target(target):
    """
    Input: target
    Output: list of intervals or []

    Parse target in the same way as Graphite, but find all interval parameters for functions 
    which accept interval: 
        hitcount(), summarize(), smartSummarize(),
        movingAverage/Min/Max/Median/Sum/Window(),
        exponentialMovingAverage()
    and return list with all of them.
    """
    from graphite.render.grammar import grammar as _grammar
    from graphite.render.attime import parseTimeOffset
    from pyparsing import ParseResults

    def flatten2list(object):
        """
        Recursively flattening list-like object
        """
        gather = []
        for item in object:
            if isinstance(item, (list, tuple, set)):
                gather.extend(flatten2list(item))            
            else:
                gather.append(item)
        return gather

    def _evaluateTokens(requestContext, tokens, replacements=None, pipedArg=None):
        """
        Simplified version of evaluateTokens() function from graphite.render.evaluator
        Parses tokens recursively, extracts 2nd argument for interval functions and
        convert it into seconds.
        """
        # same as in evaluateTokens()
        if tokens.expression:
            if tokens.expression.pipedCalls:
                rightMost = tokens.expression.pipedCalls.pop()
                return _evaluateTokens(requestContext, rightMost, replacements, tokens)
            return _evaluateTokens(requestContext, tokens.expression, replacements)
        
        # we can't fetch data here, ignoring pathExpression
        if tokens.pathExpression:
            return None

        # we have a function
        if tokens.call:
            # get function name
            func = tokens.call.funcname
            # process args in same was as in evaluateTokens()
            # we're keeping args and kwargs here because function is recursive
            rawArgs = tokens.call.args or []
            if pipedArg is not None:
                rawArgs.insert(0, pipedArg)
            args = [_evaluateTokens(requestContext, arg, replacements) for arg in rawArgs]
            requestContext['args'] = rawArgs
            kwargs = dict([(kwarg.argname, _evaluateTokens(requestContext, kwarg.args[0], replacements))
                       for kwarg in tokens.call.kwargs])
            # maybe we should switch to regex to detect function name           
            if 'oving' in func or 'hitcount' in func or 'ummarize' in func:
                if requestContext['args']:
                    log.debug("--- func:'{}'".format(func))
                    log.debug("--- requestContext['args']:*{}*".format(requestContext['args'].dump()))
                    # get second argument of function, flattening all lists
                    windowSize = flatten2list(requestContext['args'][1])[0]
                    # if still list - take first argument
                    if isinstance(windowSize, (ParseResults, list)):
                        windowSize = windowSize[0]
                    log.debug("--- windowSize {}".format(windowSize))
                    try:
                        deltaSeconds = int(windowSize)
                    except ValueError:
                        delta = parseTimeOffset(windowSize.strip('\"').strip('\''))
                        log.debug("--- delta is {}".format(delta))
                        deltaSeconds = abs(delta.seconds + (delta.days * 86400))
                    log.debug("--- deltaSeconds is {}".format(deltaSeconds))
                    # using context for accumulate results
                    requestContext['_maxStep'].append(deltaSeconds)
        return requestContext['_maxStep']

    # this code runs before real evaluateTokens(), so, supress errors for now
    try:
        result = min(_evaluateTokens({'_maxStep':[]}, _grammar.parseString(target)))
    except (KeyError,IndexError,ValueError,TypeError):
        result = None
    return result

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
            self.timeout = 1000
        try:
            cto = getattr(settings, 'IRONDB_CONNECTION_TIMEOUT_MS')
            if cto:
                self.connection_timeout = int(cto)
        except AttributeError:
            self.connection_timeout = 300
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
            self.min_rollup_span = getattr(settings, 'IRONDB_MIN_ROLLUP_SPAN')
        except AttributeError:
            self.min_rollup_span = 60  # seconds
        try:
            self.gas_url = getattr(settings, 'IRONDB_GRAPHITE_ADJUST_STEP_URL')
            self.gas = retrieve_gas(self.gas_url, self.connection_timeout, self.timeout)
        except AttributeError:
            self.gas_url = ''
            self.gas = OrderedDict()  # empty dict
        try:
            self.gas_ttl = getattr(settings, 'IRONDB_GRAPHITE_ADJUST_STEP_URL_TTL')
        except AttributeError:
            self.gas_ttl = 900  # seconds         
        try:
            self.calculate_step_from_target = getattr(settings, 'IRONDB_CALCULATE_STEP_FROM_TARGET')
        except AttributeError:
            self.calculate_step_from_target = False            
        try:
            mr = getattr(settings, 'IRONDB_MAX_RETRIES')
            if mr:
                self.max_retries = int(mr)
        except AttributeError:
            self.max_retries = 2
        try:
            self.query_log_enabled = getattr(settings, 'IRONDB_QUERY_LOG')
        except AttributeError:
            self.query_log_enabled = False
        try:
            self.zipkin_enabled = getattr(settings, 'IRONDB_ZIPKIN_ENABLED')
        except AttributeError:
            self.zipkin_enabled = False
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
        self.max_step = None


class IRONdbMeasurementFetcher(object):
    __slots__ = ('leaves','lock', 'fetched', 'results', 'headers', 'database_rollups', 'rollup_window', 'timeout', 'connection_timeout', 'retries',
                 'zipkin_enabled', 'zipkin_event_trace_level', 'max_step', 'min_rollup_span')

    def __init__(self, headers, timeout, connection_timeout, db_rollups, rollup_window, retries, zipkin_enabled, 
                zipkin_event_trace_level, max_step, min_rollup_span):
        self.leaves = list()
        self.lock = threading.Lock()
        self.fetched = False
        self.results = {}
        self.headers = {}
        self.timeout = timeout
        self.connection_timeout = connection_timeout
        self.database_rollups = db_rollups
        self.rollup_window = rollup_window
        self.min_rollup_span = min_rollup_span
        self.retries = retries
        self.zipkin_enabled = zipkin_enabled
        self.zipkin_event_trace_level = zipkin_event_trace_level
        self.max_step = max_step
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
                for i in range(0, self.retries):
                    try:
                        self.fetched = False
                        query_start = time.gmtime()
                        node = urls.series_multi
                        data_type = "json"
                        send_headers = copy.deepcopy(self.headers)
                        if self.zipkin_enabled == True:
                            traceheader = binascii.hexlify(os.urandom(8))
                            send_headers['X-B3-TraceId'] = traceheader
                            send_headers['X-B3-SpanId'] = traceheader
                            if self.zipkin_event_trace_level == 1:
                                send_headers['X-Mtev-Trace-Event'] = '1'
                            elif self.zipkin_event_trace_level == 2:
                                send_headers['X-Mtev-Trace-Event'] = '2'
                        if self.max_step:
                            params['step'] = self.max_step      
                        log.debug("- params is {}".format(params))        
                        d = requests.post(urls.series_multi, json = params, headers = send_headers,
                                          timeout=((self.connection_timeout / 1000.0), (self.timeout / 1000.0)))
                        d.raise_for_status()
                        if 'content-type' in d.headers and d.headers['content-type'] == 'application/x-flatbuffer-metric-get-result-list':
                            self.results = irondb_flatbuf.metric_get_results(d.content)
                            self.fetched = True
                            data_type = "flatbuffer"
                        else:
                            self.results = d.json()
                            self.fetched = True

                        result_count = len(self.results["series"]) if self.results else -1
                        query_type = "rollup data" if params["database_rollups"] else "raw data"
                        query_log.query_log(node, query_start, d.elapsed, result_count, json.dumps(params), query_type, data_type, start_time, end_time)
                        break
                    except (socket.gaierror, requests.exceptions.ConnectionError) as ex:
                        # on down nodes, retry on another up to "tries" times
                        log.exception("IRONdbMeasurementFetcher.fetch ConnectionError %s" % ex)
                    except requests.exceptions.ConnectTimeout as ex:
                        # on down nodes, retry on another up to "tries" times
                        log.exception("IRONdbMeasurementFetcher.fetch ConnectTimeout %s" % ex)
                    except irondb_flatbuf.FlatBufferError as ex:
                        # flatbuffer error, try again
                        log.exception("IRONdbMeasurementFetcher.fetch FlatBufferError %s" % ex)
                    except JSONDecodeError as ex:
                        # json error, try again
                        log.exception("IRONdbMeasurementFetcher.fetch JSONDecodeError %s" % ex)
                    except requests.exceptions.ReadTimeout as ex:
                        # on down nodes, retry on another up to "tries" times
                        log.exception("IRONdbMeasurementFetcher.fetch ReadTimeout %s" % ex)
                    except requests.exceptions.HTTPError as ex:
                        # http status code errors are failures, stop immediately
                        log.exception("IRONdbMeasurementFetcher.fetch HTTPError %s %s" % (ex, d.content))
                        break
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
                 'zipkin_event_trace_level', 'max_step', 'min_rollup_span',
                 'gas','gas_url','gas_ttl')

    def __init__(self, config=None):
        global urls
        global gas_next_update
        if config is not None:
            self.batch_size = 250
            self.database_rollups = True
            self.timeout = 1000
            self.connection_timeout = 300
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
            self.max_step = None
            self.min_rollup_span = 60
            self.calculate_step_from_target = False
            self.gas = OrderedDict()
            self.gas_url = ''
            self.gas_ttl = 900
        else:
            IRONdbLocalSettings.load(self)
        gas_next_update = int(time.time()) + self.gas_ttl

    def query_log(self, node, start, elapsed, result_count, query, query_type, data_format, data_start, data_end):
        if self.query_log_enabled == False:
            return

        qs = time.strftime("%Y-%m-%d %H:%M:%S", start)
        e = str(elapsed)

        log.info('******* IRONdb query -- node: %s, start: %s, result_count: %d, type: %s, format: %s, elapsed: %s\n\n  [%s, %s] "%s"\n'
                 % (node, qs, result_count, query_type, data_format, e, data_start, data_end, query))

    def newfetcher(self, fset, headers):
        fetcher = IRONdbMeasurementFetcher(headers, self.timeout, self.connection_timeout, self.database_rollups, self.rollup_window, self.max_retries,
                                           self.zipkin_enabled, self.zipkin_event_trace_level, self.max_step, self.min_rollup_span)
        fset.append(fetcher)
        return fetcher

    def dispatchfetches(self, fset, start_time, end_time):
        for fetcher in fset:
            fetcher.fetch(self, start_time, end_time)

    def fetch(self, patterns, start_time, end_time, now=None, requestContext=None):
        log.debug("IRONdbFinder.fetch called")
        # getting maxStep parameter from context, if provided      
        maxStep = requestContext.get('maxStep', None)
        if maxStep:
            log.debug("-- setting self.max_step = {} from context".format(maxStep))
            self.max_step = int(maxStep)
        elif self.calculate_step_from_target:
            # get list of targets from context
            # graphite-web should provide this
            targets = requestContext.get('targets', None)
            if targets and not self.max_step:
                max_step = -1
                for t in targets:
                    # performance shortcut
                    if 'oving' not in t or 'hitcount' not in t or 'ummarize' not in t:
                        next
                    log.debug("-- target is {}".format(t))
                    interval = find_minimal_interval_in_target(t)
                    log.debug("-- minimal interval from target '{}' is {}".format(t, interval))
                    if interval is not None:
                        if max_step < 0:
                            max_step = interval
                        if max_step < interval:
                            max_step = interval
                log.debug("-- max_step is {}".format(max_step))
                if max_step > 0:
                    # calculating span same way as IRONdb
                    # target 480 datapoints in the window and use the rollup that best matches this
                    # 480 comes from max effective resolution 1920px and no more than 1 datapoint per 4 pixels         
                    rollup_list = [1,2,5,10,15,20,30,60,120,300,600,900,1200,1800,3600,7200,10800,21600,28800,43200,86400]
                    target_datapoints = (end_time - start_time) / 480
                    if target_datapoints < self.min_rollup_span or not self.database_rollups:
                        target_datapoints = self.min_rollup_span
                    span = rollup_list[-1]    
                    for r in rollup_list:
                        if r >= target_datapoints:
                            span = r
                            break
                    log.debug("-- span is {}".format(span))
                    if max_step < span:
                        self.max_step = max_step
                    log.debug("-- setting self.max_step = {} from targets".format(max_step))
        all_names = {}
        for pattern in patterns:
            log.debug("IRONdbFinder.fetch pattern: %s" % pattern)
            names = {}
            name_headers = copy.deepcopy(self.headers)
            name_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
            for i in range(0, self.max_retries):
                try:
                    node = urls.names
                    query_start = time.gmtime()
                    data_type = "json"
                    if self.zipkin_enabled == True:
                        traceheader = binascii.hexlify(os.urandom(8))
                        name_headers['X-B3-TraceId'] = traceheader
                        name_headers['X-B3-SpanId'] = traceheader
                        if self.zipkin_event_trace_level == 1:
                            name_headers['X-Mtev-Trace-Event'] = '1'
                        if self.zipkin_event_trace_level == 2:
                            name_headers['X-Mtev-Trace-Event'] = '2'
                    name_params = {'query': pattern}
                    if self.activity_tracking:
                        name_params['activity_start_secs'] = start_time
                        name_params['activity_end_secs'] = end_time
                    r = requests.get(node, params=name_params, headers=name_headers,
                                     timeout=((self.connection_timeout / 1000.0), (self.timeout / 1000.0)))
                    r.raise_for_status()
                    if r.headers['content-type'] == 'application/json':
                        names = r.json()
                    elif r.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                        names = irondb_flatbuf.metric_find_results(r.content)
                        data_type = "flatbuffer"
                    else:
                        pass
                    result_count = len(names) if names else -1
                    self.query_log(node, query_start, r.elapsed, result_count, pattern, "names", data_type, start_time, end_time)
                    break
                except (socket.gaierror, requests.exceptions.ConnectionError) as ex:
                    # on down nodes, try again on another node until "tries"
                    log.exception("IRONdbFinder.fetch ConnectionError %s" % ex)
                except requests.exceptions.ConnectTimeout as ex:
                    # on down nodes, try again on another node until "tries"
                    log.exception("IRONdbFinder.fetch ConnectTimeout %s" % ex)
                except irondb_flatbuf.FlatBufferError as ex:
                    # flatbuffer error, try again
                    log.exception("IRONdbFinder.fetch FlatBufferError %s" % ex)
                except JSONDecodeError as ex:
                    # json error, try again
                    log.exception("IRONdbFinder.fetch JSONDecodeError %s" % ex)
                except requests.exceptions.ReadTimeout as ex:
                    # on down nodes, try again on another node until "tries"
                    log.exception("IRONdbFinder.fetch ReadTimeout %s" % ex)
                except requests.exceptions.HTTPError as ex:
                    # http status code errors are failures, stop immediately
                    log.exception("IRONdbFinder.fetch HTTPError %s %s" % (ex, r.content))
                    break

            all_names[pattern] = names

        # update graphite_adjust_step.json if url defined
        global gas_next_update
        if self.gas_url and gas_next_update <= int(time.time()):
            self.gas = retrieve_gas(self.gas_url, self.connection_timeout, self.timeout)
            gas_next_update = int(time.time()) + self.gas_ttl
        log.debug(" - gas is {}".format(str(self.gas)))

        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        in_this_batch = 0
        fset = []
        fetcher = self.newfetcher(fset, measurement_headers)
        new_step = self.max_step
        fetchers_cache = {}
        fetchers_cache[new_step] = fetcher
        for pattern, names in all_names.items():
            for name in names:
                if 'leaf' in name and 'leaf_data' in name:
                    # gas processing
                    if self.gas_url and self.gas:
                        for rex in self.gas:
                            # it's O(N^2) but I doubt we can optimize it
                            # you need to check all names against all regexes
                            # from top to bottom until first match
                            if rex.search(name['name']):
                                new_step = self.gas[rex]
                                break
                    if self.batch_size == 0 or in_this_batch >= self.batch_size or new_step != self.max_step:
                        # check do we have fetcher with proper step and not full
                        cached = fetchers_cache.get(new_step)
                        if cached and cached.max_step == new_step and len(cached.leaves) < self.batch_size:
                            # reuse it
                            in_this_batch = len(cached.leaves)
                            fetcher = cached
                        else:
                            # spawn new fetcher an add it to cache
                            in_this_batch = 0
                            self.max_step = new_step
                            fetcher = self.newfetcher(fset, measurement_headers)
                            if not fetchers_cache.get(new_step):
                                fetchers_cache[new_step] = fetcher

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
        name_headers = copy.deepcopy(self.headers)
        name_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
        for i in range(0, self.max_retries):
            try:
                if self.zipkin_enabled == True:
                    traceheader = binascii.hexlify(os.urandom(8))
                    name_headers['X-B3-TraceId'] = traceheader
                    name_headers['X-B3-SpanId'] = traceheader
                    if self.zipkin_event_trace_level == 1:
                        name_headers['X-Mtev-Trace-Event'] = '1'
                    elif self.zipkin_event_trace_level == 2:
                        name_headers['X-Mtev-Trace-Event'] = '2'
                r = requests.get(urls.names, params={'query': query.pattern}, headers=name_headers,
                                 timeout=((self.connection_timeout / 1000.0), (self.timeout / 1000.0)))
                r.raise_for_status()
                if r.headers['content-type'] == 'application/json':
                    names = r.json()
                elif r.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                    names = irondb_flatbuf.metric_find_results(r.content)
                else:
                    pass
                break
            except (socket.gaierror, requests.exceptions.ConnectionError) as ex:
                # on down nodes, try again on another node until "tries"
                log.exception("IRONdbFinder.find_nodes ConnectionError %s" % ex)
            except requests.exceptions.ConnectTimeout as ex:
                # on down nodes, try again on another node until "tries"
                log.exception("IRONdbFinder.find_nodes ConnectTimeout %s" % ex)
            except irondb_flatbuf.FlatBufferError as ex:
                # flatbuffer error, try again
                log.exception("IRONdbFinder.find_nodes FlatBufferError %s" % ex)
            except JSONDecodeError as ex:
                # json error, try again
                log.exception("IRONdbFinder.find_nodes JSONDecodeError %s" % ex)
            except requests.exceptions.ReadTimeout as ex:
                # on down nodes, try again on another node until "tries"
                log.exception("IRONdbFinder.find_nodes ReadTimeout %s" % ex)
            except requests.exceptions.HTTPError as ex:
                # http status code errors are failures, stop immediately
                log.exception("IRONdbFinder.find_nodes HTTPError %s %s" % (ex, r.content))
                break
        if settings.DEBUG:
            log.debug("IRONdbFinder.find_nodes, result: %s" % json.dumps(names))

        # for each set of self.batch_size leafnodes, execute an IRONdbMeasurementFetcher
        # so we can do these in batches.
        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        fetcher = IRONdbMeasurementFetcher(measurement_headers, self.timeout, self.connection_timeout, self.database_rollups, self.rollup_window, self.max_retries,
                                           self.zipkin_enabled, self.zipkin_event_trace_level, self.max_step, self.min_rollup_span)

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
        for i in range(0, self.max_retries):
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
                                     timeout=((self.connection_timeout / 1000.0), (self.timeout / 1000.0)))
                r.raise_for_status()
                if flatbuffers:
                    r = irondb_flatbuf.metric_find_results(r.content)
                else:
                    r = r.json()
                if settings.DEBUG:
                    log.debug("IRONdbTagFetcher.%s, result: %s" % (source, json.dumps(r)))
                return r
            except (socket.gaierror, requests.exceptions.ConnectionError) as ex:
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
                # on down nodes, try again on another node until "tries"
                log.exception("IRONdbTagFetcher.%s ReadTimeout %s" % (source, ex))
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
