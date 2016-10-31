import itertools
import time

try:
    from graphite_api.intervals import Interval, IntervalSet
    from graphite_api.node import LeafNode, BranchNode
except ImportError:
    from graphite.intervals import Interval, IntervalSet
    from graphite.node import LeafNode, BranchNode
    
from graphite.logger import log
import requests

class IronDBLeafNode(LeafNode):
    __fetch_multi__ = 'irondb'

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


class IronDBReader(object):
    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name

    def fetch(self, start_time, end_time):
        d = requests.get(urls.series, params={'name': self.name,
                                                 'start': start_time,
                                                 'end': end_time})
        data = d.json()
        if 'error' in data:
            return (start_time, end_time, end_time - start_time), []
        if len(data['series']) == 0:
            return
        time_info = data['from'], data['to'], data['step']
        return time_info, data['series'].get(self.name, [])

    def get_intervals(self):
        # all time
        return IntervalSet([Interval(0, int(time.time()))])


class IronDBFinder(object):
    __fetch_multi__ = 'irondb'

    def __init__(self, config=None):
        global urls
        if config is not None:
            if 'urls' in config['irondb']:
                urls = config['irondb']['urls']
            else:
                urls = [config['irondb']['url'].strip('/')]
        else:
            from django.conf import settings
            urls = getattr(settings, 'IRONDB_URLS')
            if not urls:
                urls = [settings.IRONDB_URL]
        urls = URLs(urls)

    def find_nodes(self, query):
        log.info("irondb.IronDBFinder.find_nodes")
        url = urls.names
        names = requests.get(url,
                             params={'query': query.pattern}).json()
        for name in names:
            if name['leaf']:
                yield IronDBLeafNode(name['name'],
                                      IronDBReader(name['name']))
            else:
                yield BranchNode(name['name'])

    def fetch_multi(self, nodes, start_time, end_time):
        log.info("irondb.IronDBFinder.fetch_multi")
        names = [node.name for node in nodes]
        data = {}
        tmpdata = requests.post(urls.series_multi,
                                   params={'name': nameslist,
                                           'start': start_time,
                                           'end': end_time}).json()
        if 'error' in tmpdata:
            return (start_time, end_time, end_time - start_time), {}

        if 'series' in data:
            data['series'].update(tmpdata['series'])
        else:
            data = tmpdata

        time_info = data['from'], data['to'], data['step']
        return time_info, data['series']
