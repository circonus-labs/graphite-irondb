import sys
import itertools
import time
import threading
import django
import copy
import json

try:
    import flatcc as irondb_flatbuf
except ImportError:
    import flatbuf as irondb_flatbuf

from graphite.intervals import Interval, IntervalSet
from graphite.node import LeafNode, BranchNode
from graphite.logger import log
try:
    from graphite.finders.utils import BaseFinder
except ImportError:
    BaseFinder = object
try:
    from graphite.tags.base import BaseTagDB
except ImportError:
    BaseTagDB = object


import json
import requests
from django.conf import settings

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError


class URLs(object):
    def __init__(self, hosts):
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
        return '{0}/tag_cats/'.format(self.host).replace('/graphite/', '/find/', 1)

    @property
    def tag_vals(self):
        return '{0}/tag_vals/'.format(self.host).replace('/graphite/', '/find/', 1)

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
        if urls is None:
            urls = getattr(settings, 'IRONDB_URLS')
            if not urls:
                urls = [settings.IRONDB_URL]
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
            self.database_rollups = getattr(settings, 'IRONDB_USE_DATABASE_ROLLUPS')
        except AttributeError:
            self.database_rollups = True
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


class IRONdbMeasurementFetcher(object):
    __slots__ = ('leaves','lock', 'fetched', 'results', 'headers', 'database_rollups', 'timeout', 'connection_timeout', 'retries')

    def __init__(self, headers, timeout, connection_timeout, db_rollups, retries):
        self.leaves = list()
        self.lock = threading.Lock()
        self.fetched = False
        self.results = {}
        self.headers = {}
        self.timeout = timeout
        self.connection_timeout = connection_timeout
        self.database_rollups = db_rollups
        self.retries = retries
        if headers:
            self.headers = headers

    def add_leaf(self, leaf_name, leaf_data):
        self.leaves.append({'leaf_name': leaf_name, 'leaf_data': leaf_data})

    def fetch(self, query_log, start_time, end_time):
        if (self.fetched == False):
            self.lock.acquire()
            # recheck in case we were waiting
            if (self.fetched == False):
                params = {}
                params['names'] = self.leaves
                params['start'] = start_time
                params['end'] = end_time
                params['database_rollups'] = self.database_rollups
                tries = self.retries
                for i in range(0, min(urls.host_count, tries)):
                    try:
                        self.fetched = False
                        query_start = time.gmtime()
                        node = urls.series_multi
                        data_type = "json"
                        d = requests.post(urls.series_multi, json = params, headers = self.headers,
                                          timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
                        d.raise_for_status()
                        if 'content-type' in d.headers and d.headers['content-type'] == 'application/x-flatbuffer-metric-get-result-list':
                            self.results = irondb_flatbuf.metric_get_results(d.content)
                            self.fetched = True
                            data_type = "flatbuffer"
                        else:
                            self.results = d.json()
                            self.fetched = True

                        result_count = len(self.results["series"]) if self.results else -1
                        query_log.query_log(node, query_start, d.elapsed, result_count, json.dumps(params), "data", data_type, start_time, end_time)
                        break
                    except requests.exceptions.ConnectionError as ex:
                        # on down nodes, retry on another up to "tries" times
                        log.debug("IRONdbMeasurementFetcher.fetch ConnectionError %s" % ex)
                    except requests.exceptions.ConnectTimeout as ex:
                        # on down nodes, retry on another up to "tries" times
                        log.debug("IRONdbMeasurementFetcher.fetch ConnectTimeout %s" % ex)
                    except JSONDecodeError as ex:
                        log.debug("IRONdbMeasurementFetcher.fetch JSONDecodeError %s" % ex)
                    except requests.exceptions.ReadTimeout as ex:
                        # read timeouts are failures, stop immediately
                        log.debug("IRONdbMeasurementFetcher.fetch ReadTimeout %s" % ex)
                        break
                    except requests.exceptions.HTTPError as ex:
                        # http status code errors are failures, stop immediately
                        log.debug("IRONdbMeasurementFetcher.fetch HTTPError %s %s" % (ex, d.content))
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
                 'connection_timeout', 'headers', 'disabled', 'max_retries')

    def __init__(self, config=None):
        global urls
        if config is not None:
            self.batch_size = 250
            self.database_rollups = True
            self.timeout = 10000
            self.connection_timeout = 3005
            self.headers = {}
            self.disabled = False
            self.max_retries = 2
            self.query_log_enabled = False
            if 'urls' in config['irondb']:
                urls = config['irondb']['urls']
            else:
                urls = [config['irondb']['url'].strip('/')]
            if 'batch_size' in config['irondb']:
                self.batch_size = config['irondb']['batch_size']
            urls = URLs(urls)
        else:
            IRONdbLocalSettings.load(self)

    def query_log(self, node, start, elapsed, result_count, query, query_type, data_format, data_start, data_end):
        if self.query_log_enabled == False:
            return

        qs = time.strftime("%Y-%m-%d %H:%M:%S", start)
        e = str(elapsed)

        log.info('******* IRONdb query -- node: %s, start: %s, result_count: %d, type: %s, format: %s, elapsed: %s\n\n  [%s, %s] "%s"\n'
                 % (node, qs, result_count, query_type, data_format, e, data_start, data_end, query))

    def fetch(self, patterns, start_time, end_time, now=None, requestContext=None):
        log.debug("IRONdbFinder.fetch called")
        all_names = {}
        for pattern in patterns:
            log.debug("IRONdbFinder.fetch pattern: %s" % pattern)
            names = {}
            tries = self.max_retries
            name_headers = copy.deepcopy(self.headers)
            name_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
            for i in range(0, min(urls.host_count, tries)):
                try:
                    node = urls.names
                    query_start = time.gmtime()
                    data_type = "json"
                    r = requests.get(node, params={'query': pattern}, headers=name_headers,
                                     timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
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
                except requests.exceptions.ConnectionError as ex:
                    # on down nodes, try again on another node until "tries"
                    log.debug("IRONdbFinder.fetch ConnectionError %s" % ex)
                except requests.exceptions.ConnectTimeout as ex:
                    # on down nodes, try again on another node until "tries"
                    log.debug("IRONdbFinder.fetch ConnectTimeout %s" % ex)
                except requests.exceptions.ReadTimeout as ex:
                    # up node that simply timed out is a failure
                    log.debug("IRONdbFinder.fetch ReadTimeout %s" % ex)
                    break
                except requests.exceptions.HTTPError as ex:
                    # http status code errors are failures, stop immediately
                    log.debug("IRONdbFinder.fetch HTTPError %s %s" % (ex, r.content))
                    break

            all_names[pattern] = names

        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        fetcher = IRONdbMeasurementFetcher(measurement_headers, self.timeout, self.connection_timeout, self.database_rollups, self.max_retries)
        for pattern, names in all_names.items():
            for name in names:
                if 'leaf' in name and 'leaf_data' in name:
                    fetcher.add_leaf(name['name'], name['leaf_data'])

        fetcher.fetch(self, start_time, end_time)

        results = []
        for pattern, names in all_names.items():
            for name in names:
                res = fetcher.series(name['name'])
                if res is None:
                    continue

                time_info, values = res
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
        names = {}
        tries = self.max_retries
        name_headers = copy.deepcopy(self.headers)
        name_headers['Accept'] = 'application/x-flatbuffer-metric-find-result-list'
        for i in range(0, min(urls.host_count, tries)):
            try:
                r = requests.get(urls.names, params={'query': query.pattern}, headers=name_headers,
                                 timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
                r.raise_for_status()
                if r.headers['content-type'] == 'application/json':
                    names = r.json()
                elif r.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                    names = irondb_flatbuf.metric_find_results(r.content)
                else:
                    pass
                break
            except requests.exceptions.ConnectionError as ex:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbFinder.find_nodes ConnectionError %s" % ex)
            except requests.exceptions.ConnectTimeout as ex:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbFinder.find_nodes ConnectTimeout %s" % ex)
            except requests.exceptions.ReadTimeout as ex:
                # up node that simply timed out is a failure
                log.debug("IRONdbFinder.find_nodes ReadTimeout %s" % ex)
                break
            except requests.exceptions.HTTPError as ex:
                # http status code errors are failures, stop immediately
                log.debug("IRONdbFinder.find_nodes HTTPError %s %s" % (ex, r.content))
                break
        if settings.DEBUG:
            log.debug("IRONdbFinder.find_nodes, result: %s" % json.dumps(names))

        # for each set of self.batch_size leafnodes, execute an IRONdbMeasurementFetcher
        # so we can do these in batches.
        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        fetcher = IRONdbMeasurementFetcher(measurement_headers, self.timeout, self.connection_timeout, self.database_rollups, self.max_retries)

        for name in names:
            if 'leaf' in name and 'leaf_data' in name:
                fetcher.add_leaf(name['name'], name['leaf_data'])
                reader = IRONdbReader(name['name'], fetcher)
                yield LeafNode(name['name'], reader)
            else:
                yield BranchNode(name['name'])


class IRONdbTagFetcher(BaseTagDB):

    def __init__(self, settings, *args, **kwargs):
        super(IRONdbTagFetcher, self).__init__(settings, *args, **kwargs)
        IRONdbLocalSettings.load(self)

    def _request(self, url, query):
        if not isinstance(query, dict):
            query = {'query': query}
        source = ""
        if settings.DEBUG:
            source = sys._getframe().f_back.f_code.co_name
        tries = self.max_retries
        for i in range(0, min(urls.host_count, tries)):
            try:
                r = requests.get(url, params=query, headers=self.headers,
                                     timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
                r.raise_for_status()
                r = r.json()
                if settings.DEBUG:
                    log.debug("IRONdbTagFetcher.%s, result: %s" % (source, json.dumps(r)))
                return r
            except requests.exceptions.ConnectionError as ex:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbTagFetcher.%s ConnectionError %s" % (source, ex))
            except requests.exceptions.ConnectTimeout as ex:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbTagFetcher.%s ConnectTimeout %s" % (source, ex))
            except requests.exceptions.ReadTimeout as ex:
                # up node that simply timed out is a failure
                log.debug("IRONdbTagFetcher.%s ReadTimeout %s" % (source, ex))
                break
            except requests.exceptions.HTTPError as ex:
                # http status code errors are failures, stop immediately
                log.debug("IRONdbTagFetcher.%s HTTPError %s %s" % (source, ex, r.content))
                break
        return ()

    def _find_series(self, tags, requestContext=None):
        query = ','.join(tags)
        tag_series = self._request(urls.tags, query)
        return [series['name'] for series in tag_series]

    def list_tags(self, tagFilter=None, limit=None, requestContext=None):
        query = 'and(*:*)'
        tag_cats = self._request(urls.tag_cats, query)
        return [{'tag': tag} for tag in tag_cats]

    def get_tag(self, tag, valueFilter=None, limit=None, requestContext=None):
        query = {'query': 'and(*:*)', 'category': tag}
        tag_vals = self._request(urls.tag_vals, query)
        if not tag_vals:
            return None
        res = []
        for val in tag_vals:
            tag_series = self._request(urls.tags, '%s=%s' % (tag, val))
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
