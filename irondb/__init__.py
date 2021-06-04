try:
    import graphite
except ImportError:
    pass
else:
    from irondb.irondb import *
    __all__ = ['IRONdbFinder', 'IronDBFinder', 'IRONdbTagFetcher', 'IronDBTagFetcher']
