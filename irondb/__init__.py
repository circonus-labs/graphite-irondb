try:
    import graphite
except ImportError:
    pass
else:
    from irondb import *
    __all__ = ['IRONdbFinder', 'IronDBFinder', 'IRONdbTagFetcher', 'IronDBTagFetcher']
