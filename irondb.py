import itertools
import time
import threading
import django

from graphite.intervals import Interval, IntervalSet
from graphite.node import LeafNode, BranchNode

try:
    from graphite.logger import log
except django.core.exceptions.ImproperlyConfigured:
    print "No graphite logger"

import requests

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
    def host_count(self):
        return self.hc

urls = None
urllength = 4096

class IronDBMeasurementFetcher(object):
    __slots__ = ('leaves','lock', 'fetched', 'results', 'headers', 'database_rollups')

    def __init__(self, headers, db_rollups):
        self.leaves = list()
        self.lock = threading.Lock()
        self.fetched = False
        self.results = {}
        self.headers = {}
        self.database_rollups = db_rollups
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
                for i in range(0, urls.host_count):
                    try:
                        d = requests.post(urls.series_multi, json = params, headers = self.headers)
                        self.results = d.json()
                        self.fetched = True
                        break
                    except ConnectionError:
                        # on down nodes, try again on another node until we try them all
                        pass
            self.lock.release()
    def is_error(self):
        return self.results == None or 'error' in self.results

    def series(self, name):
        if self.is_error() or len(self.results['series']) == 0:
            return

        time_info = self.results['from'], self.results['to'], self.results['step']
        if len(self.results['series'].get(name, [])) == 0:
            return time_info, [None] * ((self.results['to'] - self.results['from']) / self.results['step'])

        return time_info, self.results['series'].get(name, [])

class IronDBReader(object):
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


class IronDBFinder(object):

    def __init__(self, config=None):
        global urls
        self.batch_size = 250
        self.database_rollups = True
        if config is not None:
            if 'urls' in config['irondb']:
                urls = config['irondb']['urls']
            else:
                urls = [config['irondb']['url'].strip('/')]
            if 'batch_size' in config['irondb']:
                self.batch_size = config['irondb']['batch_size']
        else:
            from django.conf import settings
            urls = getattr(settings, 'IRONDB_URLS')
            if not urls:
                urls = [settings.IRONDB_URL]
            try:
                bs = getattr(settings, 'IRONDB_BATCH_SIZE')
                if bs:
                    self.batch_size = int(bs)
            except AttributeError:
                self.batch_size = 250
            try:
                token = getattr(settings, 'CIRCONUS_TOKEN')
		self.headers = {}
                if token:
                    self.headers = { 'X-Circonus-Auth-Token': token, 'X-Circonus-App-Name': 'graphite-web' }
            except AttributeError:
                self.headers = {}
            try:
                self.database_rollups = getattr(settings, 'IRONDB_USE_DATABASE_ROLLUPS')
            except AttributeError:
                self.database_rollups = True

        urls = URLs(urls)

    def find_nodes(self, query):
        names = {}
        for i in range(0, urls.host_count):
            try:
                names = requests.get(urls.names, params={'query': query.pattern}, headers=self.headers).json()
                break
            except ConnectionError:
                # on down nodes, try again on another node until we try them all
                pass

        # for each set of self.batch_size leafnodes, execute an IronDBMeasurementFetcher
        # so we can do these in batches.
        counter = 0
        fetcher = IronDBMeasurementFetcher(self.headers, self.database_rollups)

        for name in names:
            if name['leaf']:
                fetcher.add_leaf(name['name'], name['leaf_data'])
                reader = IronDBReader(name['name'], fetcher)
                counter = counter + 1
                if (counter % self.batch_size == 0):
                    fetcher = IronDBMeasurementFetcher(self.headers, self.database_rollups)
                    counter = 0
                yield LeafNode(name['name'], reader)
            else:
                yield BranchNode(name['name'])
