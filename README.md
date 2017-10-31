Graphite-IronDB
================

A plugin for using graphite with the IronDB from Circonus.

Requires Graphite-web 0.10.X.

Graphite-web 0.10.X is currently unreleased. You'll need to install
from source.

Installation
------------

```
$ git clone http://github.com/circonus-labs/graphite-irondb
$ cd graphite-irondb
$ sudo python setup.py install
```

Using with graphite-web
-----------------------

In your graphite's `local_settings.py`:

    STORAGE_FINDERS = (
        'irondb.IronDBFinder',
    )

    IRONDB_URLS = (
        'http://<irondb-host>:<port>/graphite/<account>/<optional_query_prefix>',
    )

    CIRCONUS_TOKEN = '0005cc1f-5b27-4b60-937b-7c73a25dfef7'

    IRONDB_BATCH_SIZE = 250
    IRONDB_USE_DATABASE_ROLLUPS = True
    IRONDB_TIMEOUT_MS = 10000
    IRONDB_CONNECTION_TIMEOUT_MS = 3005
    IRONDB_MAX_RETRIES = 2

Where `irondb-host` is the DNS or IP of an IronDB node, `port`
(usually 8112) is the listening port for IronDB, and <account> is some
integer you have been ingesting your metrics under (see Namespacing in
the IronDB docs).  `optional_query_prefix` can be used to prefix all
operations with a fixed name.  You can use this optional prefix to
simplify metric names stored in IRONdb.  If you just want raw names
as stored in IRONdb, you can omit this last URL section (see
Graphite Rendering in the IRONdb documentation).

If you have a multi-node IronDB installation (likely), you should
specify multiple URLS (one for each node in the cluster), or place the
IronDB installation behind a load balancer.  For example,

    IRONDB_URLS = (
        'http://host1:8112/graphite/1',
        'http://host2:8112/graphite/1',
    )

NOTE: the `IRONDB_URLS` is a python list and therefore must end with a 
trailing comma on the last entry.

If you are pointing graphite at a Circonus SaaS account, set the token
to a valid Circonus Auth Token and set the URL to the public API URL.
Your tokens can be managed under your account at
https://login.circonus.com/user/tokens .  Note that the storage finder will
not work if the application 'graphite' is not approved.  If you find it not
working, visit your tokens page and refresh to find the graphite application
and manually approve it.

    CIRCONUS_TOKEN = '<your-token-uuid>'
    IRONDB_URLS = (
        'https://api.circonus.com/graphite',
    )

`IRONDB_BATCH_SIZE` is optional and will default to 250.  Batch size is
used to perform multi-fetch from the IronDB backend if you use graphs
with wildcard expansions in the datapoints.

`IRONDB_USE_DATABASE_ROLLUPS` is optional python boolean (True|False)
and will default to True. IRONdb can automatically choose the "step"
of the returned data if this param is set to True.  Calculation for
"step" is based on the time span of the query.  If you set this to
False, IRONdb will return the minimum rollup span it is configured to
return for all data.  This can result in slower renders as much more
data will be returned than may be necessary for rendering.  However,
some graphite functions (like summarize) require finer resolution data
in order to group data properly.

`IRONDB_TIMEOUT_MS` is optional and will default to 10000.  With IRONdb >= 0.9.8
this will set an absolute timeout after which queries will be cut off.

`IRONDB_CONNECTION_TIMEOUT_MS` is optional and will default to 3005.

`IRONDB_MAX_RETRIES` is optional and will default to 2.  Only failures to 
connect are retried (see `IRONDB_CONNECTION_TIMEOUT_MS`).  Timeouts or
other failures are not retried to prevent thundering herd problems.

Changelog
---------

* **0.0.1** (2016-11-10): initial version.
* **0.0.2** (2017-05-25): fix queries where there is no data for one or more of the requested time series
* **0.0.3** (2017-06-27): Add `CIRCONUS_TOKEN` support and `IRONDB_USE_DATABASE_ROLLUPS`
* **0.0.4** (2017-06-28): Pass more info back to IRONdb on fetches so the database doesn't have to re-lookup metric ownership among the nodes
* **0.0.5** (2017-09-01): Retry requests to irondb against different nodes if we encounter connection issues or timeouts on requests
* **0.0.6** (2017-09-11): Pass a timeout to IRONdb on all fetch operations.  This requires IRONdb >= 0.9.8
* **0.0.7** (2017-09-13): Use a separate connection timeout on all fetch operations.
* **0.0.8** (2017-09-13): Introduce `IRONDB_MAX_RETRIES`
