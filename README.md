Graphite-IRONdb
================

[![Build Status](https://travis-ci.org/circonus-labs/graphite-irondb.svg?branch=master)](https://travis-ci.org/circonus-labs/graphite-irondb)

A plugin for using graphite with the IRONdb from Circonus.

Supports Graphite-web 0.9.x, 1.0.x and 1.1.X.

Installation
------------

First, checkout the code:
```
$ git clone http://github.com/circonus-labs/graphite-irondb
$ cd graphite-irondb
```
(With no options provided, the install will look for a [`flatcc`](https://github.com/dvidelabs/flatcc) library in `/opt/circonus`)

Then, to install using [`flatcc`](https://github.com/dvidelabs/flatcc) library for FlatBuffers:
```
$ sudo python setup.py install --with-flatcc=PREFIX
```
**Or:** To install as pure Python:
```
$ sudo python setup.py install --pure-python
```
The use of `--pure-python` is provided for convenience; However, the native C module is recommended for best performance.

Using with graphite-web
-----------------------

In your graphite's `local_settings.py`:

    STORAGE_FINDERS = (
        'irondb.IRONdbFinder',
    )

    TAGDB = 'irondb.IRONdbTagFetcher'

    IRONDB_URLS = (
        'http://<irondb-host>:<port>/graphite/<account>/<optional_query_prefix>',
    )

    # Optional.  You need CIRCONUS_TOKEN if you are using this with the 
    # Circonus Saas or Inside products.  See below.
    # If you are not using Circonus SaaS or Inside you can omit this setting
    CIRCONUS_TOKEN = '0005cc1f-5b27-4b60-937b-7c73a25dfef7'

    IRONDB_BATCH_SIZE = 250
    IRONDB_USE_DATABASE_ROLLUPS = True
    IRONDB_USE_ACTIVITY_TRACKING = True
    IRONDB_TIMEOUT_MS = 10000
    IRONDB_CONNECTION_TIMEOUT_MS = 3005
    IRONDB_MAX_RETRIES = 2
    IRONDB_QUERY_LOG = False
    IRONDB_URLS_ROTATE = True
    AUTOCOMPRESS_GAPS_IN_DERIVATIVE_FUNCTIONS=True

Where `irondb-host` is the DNS or IP of an IRONdb node, `port`
(usually 8112) is the listening port for IRONdb, and <account> is some
integer you have been ingesting your metrics under (see Namespacing in
the IRONdb docs).  `optional_query_prefix` can be used to prefix all
operations with a fixed name.  You can use this optional prefix to
simplify metric names stored in IRONdb.  If you just want raw names
as stored in IRONdb, you can omit this last URL section (see
Graphite Rendering in the IRONdb documentation).

If you have a multi-node IRONdb installation (likely), you should
specify multiple URLS (one for each node in the cluster), or place the
IRONdb installation behind a load balancer.  For example,

    IRONDB_URLS = (
        'http://host1:8112/graphite/1',
        'http://host2:8112/graphite/1',
    )

NOTE: the `IRONDB_URLS` is a python list and therefore must end with a 
trailing comma on the last entry.

If you are pointing graphite at a Circonus SaaS account, set the token
to a valid Circonus Auth Token and set the URL to the public API URL
(`https://api.circonus.com/irondb/graphite`).
Your tokens can be managed under your account at
`https://login.circonus.com/user/tokens`.  Note that the storage finder will
not work if the application 'graphite' is not approved.  If you find it not
working, visit your tokens page and refresh to find the graphite application
and manually approve it.

    CIRCONUS_TOKEN = '<your-token-uuid>'
    IRONDB_URLS = (
        'https://api.circonus.com/irondb/graphite',
    )

`IRONDB_BATCH_SIZE` is optional and will default to 250.  Batch size is
used to perform multi-fetch from the IRONdb backend if you use graphs
with wildcard expansions in the datapoints.

`IRONDB_USE_DATABASE_ROLLUPS` is an optional Python boolean (True|False)
and will default to True. IRONdb can automatically choose the "step"
of the returned data if this param is set to True.  The calculation for
"step" is based on the time span of the query.  If you set this to
False, IRONdb will return the minimum rollup span it is configured to
return for all data.  This can result in slower renders as much more
data will be returned than may be necessary for rendering.  However,
some graphite functions (like `summarize()`) require finer resolution data
to group data properly (but now you can use `IRONDB_CALCULATE_STEP_FROM_TARGET`)
 to fix that problem (see next section).

`IRONDB_CALCULATE_STEP_FROM_TARGET` is an optional Python boolean (True|False)
and will default to False. If enabled and if `IRONDB_USE_DATABASE_ROLLUPS=True` 
the step will be calculated by parsing the target function, extracting `windowSize` and 
`intervalString` parameter from functions and picking minimal value, i.e. in that 
case you will get the proper result of aggregating functions even if database rollups are enabled.

`IRONDB_MIN_ROLLUP_SPAN` minimal rollup span for irondb data. Used in step calculation, default is 60.

`IRONDB_GRAPHITE_ADJUST_STEP_URL` - URL to `graphite_adjust_step.json` file. If it is present then metrics will be grouped during retrieve phase by step parameter, so, IronDB would return proper results. If empty or not retrievable, then grouping functionality will be disabled. Can be absolute URL or relative to `IRONDB_URL` (if not starting with "http"). I.e., if `IRONDB_URL` is "http://host/graphite/userid/" then if `graphite_adjust_step.json` is serving from "http://host/graphite_adjust_step.json" then `IRONDB_GRAPHITE_ADJUST_STEP_URL` should be "../../graphite_adjust_step.json".  Also, in case of multiple URLs in `IRONDB_URL` file will be loaded from every URL in round-robin fashion, same as API calls.

`IRONDB_GRAPHITE_ADJUST_STEP_URL_TTL` - the number of seconds to cache content of retrieved `graphite_adjust_step.json` file. Default is 900 (15 minutes). If the refresh attempt is unsuccessful, it will disable grouping functionality until next successful retrieve attempt.

`IRONDB_USE_ACTIVITY_TRACKING` is an optional Python boolean (True|False)
and will default to True. IRONdb supports tracking of metric activity without
the expense of reading all known time series data to find active ranges.

`IRONDB_CONNECTION_TIMEOUT_MS` is optional and is the number of milliseconds the plugin will wait to establish a connection to an IronDB URL. Before version 0.0.22, the default was 3005 ms. Now it's dropped to 300 ms, assuming IronDB is located in the LAN network close to Graphite server, so in case of WAN connection, please increase it.

`IRONDB_TIMEOUT_MS` is the number of milliseconds the plugin will wait for IronDB to send a response, or any pause between bytes of the response (typically time until first byte).  Default 1000 ms. Please note this is not an absolute connection length timeout. Please see [Graphite parameters](https://graphite.readthedocs.io/en/latest/config-local-settings.html) 
`FIND_TIMEOUT` (default 3 seconds) and `FETCH_TIMEOUT` (default 6 seconds) to set absolute find or fetch timeout accordingly.

`IRONDB_MAX_RETRIES` is optional and will default to 2. Please note that plugin will retry next host in `IRONDB_URLS` list in case of connection/read timeout or data decode error (but not HTTP error).

`IRONDB_URLS_ROTATE` is also optional and if enabled will pseudorandomly rotate list of URLs in
`IRONDB_URLS` for every instance of plugin, effectively balancing HTTP requests between them.

`IRONDB_QUERY_LOG` is optional and will default to False.  Will log out
all queries to the IRONdb backend nodes into the info.log if this is set
to `True`.

`IRONDB_ZIPKIN_ENABLED` is optional and will default to False. Will send
Zipkin headers to the IRONdb nodes that are being queried.

`IRONDB_ZIPKIN_EVENT_TRACE_LEVEL` is optional and will default to 0. If
`IRONDB_ZIPKIN_ENABLED` is set to False, this flag will do nothing. If it
is set to True, this will send headers to the IRONdb nodes that will
enable additional event tracing. Right now, the only acceptable values
are `0` (off), `1` (basic tracing), and `2` (detailed tracing). `2` can
potentially cause performance issues - use this level sparingly. Only
recommended for when trying to debug something specific.



Changelog
---------

* **0.0.1** (2016-11-10): initial version.
* **0.0.2** (2017-05-25): fix queries where there is no data for one or more of the requested time series
* **0.0.3** (2017-06-27): Add `CIRCONUS_TOKEN` support and `IRONDB_USE_DATABASE_ROLLUPS`
* **0.0.4** (2017-06-28): Pass more info back to IRONdb on fetches so the database doesn't have to re-lookup metric ownership among the nodes
* **0.0.5** (2017-09-01): Retry requests to IRONdb against different nodes if we encounter connection issues or timeouts on requests
* **0.0.6** (2017-09-11): Pass a timeout to IRONdb on all fetch operations.  This requires IRONdb >= 0.9.8
* **0.0.7** (2017-09-13): Use a separate connection timeout on all fetch operations.
* **0.0.8** (2017-09-13): Introduce `IRONDB_MAX_RETRIES`
* **0.0.9** (2017-11-13): API fix for large fetches, reduce errors by catching more connection failure conditions, thanks @cbowman0
* **0.0.10** (2017-11-21): Fix sending of X-Snowth-Timeout header
* **0.0.11** (2018-04-09): Allow handling Flatbuffer data coming from IRONdb
* **0.0.12** (2018-04-16): Performance improvements to Flatbuffer via native C modules instead of native Python. Requires flatcc
* **0.0.13** (2018-04-17): Fix memory leaks in native C Flatbuffer module
* **0.0.14** (2018-07-31): Graphite 1.1 compatibility including tag support
* **0.0.15** (2018-09-14): `IRONDB_QUERY_LOG` support
* **0.0.16** (2018-12-06): Improve error handling. Fix tag categories
* **0.0.17** (2019-01-23): Fix flatcc native Flatbuffer module
* **0.0.18** (2019-02-20): Improve FlatBuffers support. Fix metric prefix handling. Use Graphite error log
* **0.0.19** (2019-03-05): Improve FlatBuffer error handling. Add Zipkin header support
* **0.0.20** (2019-05-03): Don't issue IRONdb series requests for empty find results, Add `IRONDB_ROLLUP_WINDOW` setting, Respect `IRONDB_BATCH_SIZE` setting, fix fetcher keyerror, use first start time when all series arrive late
* **0.0.21** (2019-05-14): Fix memory leak introduced in 0.0.20
* **0.0.22** (2021-06-15): Timeout fixes and URL rotation added.
