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
    
urls = None
urllength = 4096

class IronDBMeasurementFetcher(object):
    __slots__ = ('leaves','lock', 'fetched', 'results',)
    
    def __init__(self):
        self.leaves = list()
        self.lock = threading.Lock()
        self.fetched = False
        self.results = {}

    def add_leaf(self, leaf_name):
        self.leaves.append(leaf_name)

    def fetch(self, start_time, end_time):
        if (self.fetched == False):
            self.lock.acquire()
            # recheck in case we were waiting
            if (self.fetched == False):
                params = {}
                params['names'] = self.leaves
                params['start'] = start_time
                params['end'] = end_time
                d = requests.post(urls.series_multi, json = params)
                self.results = d.json()
                self.fetched = True
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
                
        urls = URLs(urls)

    def find_nodes(self, query):
        url = urls.names
        names = requests.get(url, params={'query': query.pattern}).json()
        # for each set of self.batch_size leafnodes, execute an IronDBMeasurementFetcher
        # so we can do these in batches.
        counter = 0
        fetcher = IronDBMeasurementFetcher()
                
        for name in names:
            if name['leaf']:
                fetcher.add_leaf(name['name'])
                reader = IronDBReader(name['name'], fetcher)
                counter = counter + 1
                if (counter % self.batch_size == 0):
                    fetcher = IronDBMeasurementFetcher()
                    counter = 0                
                yield LeafNode(name['name'], reader)
            else:
                yield BranchNode(name['name'])

