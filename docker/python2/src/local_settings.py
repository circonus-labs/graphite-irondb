STORAGE_FINDERS = (
    'irondb.IRONdbFinder',
)
SECRET_KEY = 'circonus'
TAGDB = 'irondb.IRONdbTagFetcher'

IRONDB_URLS = (
    'https://api.circonus.com/irondb/graphite',
)

# Optional.  You need CIRCONUS_TOKEN if you are using this with the 
# Circonus Saas or Inside products.  See below.
# If you are not using Circonus SaaS or Inside you can omit this setting
CIRCONUS_TOKEN = 'ef2c6424-4ece-4844-9dc3-8f3c8f770ea7'

IRONDB_BATCH_SIZE = 250
IRONDB_USE_DATABASE_ROLLUPS = True
IRONDB_USE_ACTIVITY_TRACKING = True
IRONDB_TIMEOUT_MS = 10000
IRONDB_CONNECTION_TIMEOUT_MS = 3005
IRONDB_MAX_RETRIES = 2
IRONDB_QUERY_LOG = False
IRONDB_URLS_ROTATE = True