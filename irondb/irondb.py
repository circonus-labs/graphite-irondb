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

    def fetch(self, start_time, end_time):
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
                        d = requests.post(urls.series_multi, json = params, headers = self.headers,
                                          timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
                        if 'content-type' in d.headers and d.headers['content-type'] == 'application/x-flatbuffer-metric-get-result-list':
                            self.results = irondb_flatbuf.metric_get_results(d.content)
                            self.fetched = True
                        else:
                            self.results = d.json()
                            self.fetched = True
                        break
                    except requests.exceptions.ConnectionError:
                        # on down nodes, retry on another up to "tries" times
                        pass
                    except requests.exceptions.ConnectTimeout:
                        # on down nodes, retry on another up to "tries" times
                        pass
                    except JSONDecodeError:
                        pass
                    except requests.exceptions.ReadTimeout:
                        # read timeouts are failures, stop immediately
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
            if 'urls' in config['irondb']:
                urls = config['irondb']['urls']
            else:
                urls = [config['irondb']['url'].strip('/')]
            if 'batch_size' in config['irondb']:
                self.batch_size = config['irondb']['batch_size']
            urls = URLs(urls)
        else:
            IRONdbLocalSettings.load(self)

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
                    r = requests.get(urls.names, params={'query': pattern}, headers=name_headers,
                                     timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
                    if r.headers['content-type'] == 'application/json':
                        names = r.json()
                    elif r.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                        names = irondb_flatbuf.metric_find_results(r.content)
                    else:
                        pass
                    break
                except requests.exceptions.ConnectionError:
                    # on down nodes, try again on another node until "tries"
                    log.debug("IRONdbFinder.fetch ConnectionError")
                except requests.exceptions.ConnectTimeout:
                    # on down nodes, try again on another node until "tries"
                    log.debug("IRONdbFinder.fetch ConnectTimeout")
                except requests.exceptions.ReadTimeout:
                    # up node that simply timed out is a failure
                    log.debug("IRONdbFinder.fetch ReadTimeout")
                    break

            all_names[pattern] = names

        measurement_headers = copy.deepcopy(self.headers)
        measurement_headers['Accept'] = 'application/x-flatbuffer-metric-get-result-list'
        fetcher = IRONdbMeasurementFetcher(measurement_headers, self.timeout, self.connection_timeout, self.database_rollups, self.max_retries)
        for pattern, names in all_names.items():
            for name in names:
                if 'leaf' in name and 'leaf_data' in name:
                    fetcher.add_leaf(name['name'], name['leaf_data'])

        fetcher.fetch(start_time, end_time)

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
                if r.headers['content-type'] == 'application/json':
                    names = r.json()
                elif r.headers['content-type'] == 'application/x-flatbuffer-metric-find-result-list':
                    names = irondb_flatbuf.metric_find_results(r.content)
                else:
                    pass
                break
            except requests.exceptions.ConnectionError:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbFinder.find_nodes ConnectionError")
            except requests.exceptions.ConnectTimeout:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbFinder.find_nodes ConnectTimeout")
            except requests.exceptions.ReadTimeout:
                # up node that simply timed out is a failure
                log.debug("IRONdbFinder.find_nodes ReadTimeout")
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
        source = ""
        if settings.DEBUG:
            source = sys._getframe().f_back.f_code.co_name
        tries = self.max_retries
        for i in range(0, min(urls.host_count, tries)):
            try:
                r = requests.get(url, params={'query': query}, headers=self.headers,
                                     timeout=((self.connection_timeout / 1000), (self.timeout / 1000)))
            except requests.exceptions.ConnectionError:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbTagFetcher.%s ConnectionError" % source)
            except requests.exceptions.ConnectTimeout:
                # on down nodes, try again on another node until "tries"
                log.debug("IRONdbTagFetcher.%s ConnectTimeout" % source)
            except requests.exceptions.ReadTimeout:
                # up node that simply timed out is a failure
                log.debug("IRONdbTagFetcher.%s ReadTimeout" % source)
                break
        r = r.json()
        if settings.DEBUG:
            log.debug("IRONdbTagFetcher.%s, result: %s" % (source, json.dumps(r)))
        return r

    def _find_series(self, tags, requestContext=None):
        query = ','.join(tags)
        tag_series = self._request(urls.tags, query)
        return [series['name'] for series in tag_series]

    def list_tags(self, tagFilter=None, limit=None, requestContext=None):
        query = 'and(*:*)'
        tag_cats = self._request(urls.tag_cats, query)
        return [{'tag': tag} for tag in tag_cats]

    # FIXME count
    def get_tag(self, tag, valueFilter=None, limit=None, requestContext=None):
        query = 'and(%s:*)' % tag
        tag_vals = self._request(urls.tag_vals, query)
        return {'tag': tag, 'values': [{'value': val, 'count': 1} for val in tag_vals]}

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
