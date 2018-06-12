Graphite-IRONdb
================

[![Build Status](https://travis-ci.org/circonus-labs/graphite-irondb.svg?branch=master)](https://travis-ci.org/circonus-labs/graphite-irondb)

A plugin for using graphite with the IRONdb from Circonus.

Requires Graphite-web 1.1.X.

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
The use of `--with-python` is provided for convenience; However, the native C module is recommended for best performance.

Using with graphite-web
-----------------------

In your graphite's `local_settings.py`:

    STORAGE_FINDERS = (
        'irondb.IronDBFinder',
    )

    IRONDB_URLS = (
        'http://<irondb-host>:<port>/graphite/<account>/<optional_query_prefix>',
    )

    # Optional.  You need CIRCONUS_TOKEN if you are using this with the 
    # Circonus Saas or Inside products.  See below.
    # If you are not using Circonus SaaS or Inside you can omit this setting
    CIRCONUS_TOKEN = '0005cc1f-5b27-4b60-937b-7c73a25dfef7'

    IRONDB_BATCH_SIZE = 250
    IRONDB_USE_DATABASE_ROLLUPS = True
    IRONDB_TIMEOUT_MS = 10000
    IRONDB_CONNECTION_TIMEOUT_MS = 3005
    IRONDB_MAX_RETRIES = 2

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
* **0.0.5** (2017-09-01): Retry requests to IRONdb against different nodes if we encounter connection issues or timeouts on requests
* **0.0.6** (2017-09-11): Pass a timeout to IRONdb on all fetch operations.  This requires IRONdb >= 0.9.8
* **0.0.7** (2017-09-13): Use a separate connection timeout on all fetch operations.
* **0.0.8** (2017-09-13): Introduce `IRONDB_MAX_RETRIES`
* **0.0.9** (2017-11-13): API fix for large fetches, reduce errors by catching more connection failure conditions, thanks @cbowman0
* **0.0.10** (2017-11-21): Fix sending of X-Snowth-Timeout header
* **0.0.11** (2018-04-09): Allow handling Flatbuffer data coming from IRONdb
* **0.0.12** (2018-04-16): Performance improvements to Flatbuffer via native C modules instead of native Python. Requires flatcc
* **0.0.13** (2018-04-17): Fix memory leaks in native C Flatbuffer module
* **0.0.X** (Unreleased): Graphite 1.1 compatibility
