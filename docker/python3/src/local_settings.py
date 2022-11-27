import os
import random
import string

_SECRET_KEY = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
SECRET_KEY = os.environ.get('GRAPHITE_SECRET_KEY', _SECRET_KEY)

FIND_TIMEOUT = os.environ.get('GRAPHITE_FIND_TIMEOUT', 10.0)
FETCH_TIMEOUT = os.environ.get('GRAPHITE_FETCH_TIMEOUT', 60.0)

DEBUG = os.environ.get('GRAPHITE_DEBUG', 'false').lower() in ['1', 'true', 'yes']

STORAGE_FINDERS = (
    'irondb.IRONdbFinder',
)
TAGDB = 'irondb.IRONdbTagFetcher'
if (os.getenv("IRONDB_URLS") is not None):
    IRONDB_URLS = os.getenv("IRONDB_URLS").split(",")
else:
    IRONDB_URLS = (
        'https://api.circonus.com/irondb/graphite',
    )

# Optional.  You need CIRCONUS_TOKEN if you are using this with the 
# Circonus Saas or Inside products.  See below.
# If you are not using Circonus SaaS or Inside you can omit this setting
CIRCONUS_TOKEN = os.environ.get('IRONDB_CIRCONUS_TOKEN', '')

IRONDB_BATCH_SIZE = os.environ.get('IRONDB_BATCH_SIZE', 250)
IRONDB_USE_DATABASE_ROLLUPS = os.environ.get('IRONDB_USE_DATABASE_ROLLUPS', 'true').lower() in ['1', 'true', 'yes']
IRONDB_USE_ACTIVITY_TRACKING = os.environ.get('IRONDB_USE_ACTIVITY_TRACKING', 'true').lower() in ['1', 'true', 'yes']
IRONDB_TIMEOUT_MS = os.environ.get('IRONDB_TIMEOUT_MS', 10000)
IRONDB_MIN_ROLLUP_SPAN = os.environ.get('IRONDB_MIN_ROLLUP_SPAN', 2)
IRONDB_CONNECTION_TIMEOUT_MS = os.environ.get('IRONDB_CONNECTION_TIMEOUT_MS', 2)
IRONDB_MAX_RETRIES = os.environ.get('IRONDB_MAX_RETRIES', 2)
IRONDB_QUERY_LOG = os.environ.get('IRONDB_QUERY_LOG', 'false').lower() in ['1', 'true', 'yes']
IRONDB_URLS_ROTATE = os.environ.get('IRONDB_URLS_ROTATE', 'true').lower() in ['1', 'true', 'yes']