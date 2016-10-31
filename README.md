Graphite-IronDB
================

A plugin for using graphite with the IronDB from Circonus.

Requires `Graphite-API`_ **(preferred)** or Graphite-web 0.10.X.

Graphite-API is available on PyPI. Read the `documentation`_ for more
information.

Graphite-web 0.10.X is currently unreleased. You'll need to install from
source.

.. _Graphite-API: https://github.com/brutasse/graphite-api
.. _documentation: https://graphite-api.readthedocs.io/en/latest/

Installation
------------

::

    pip install graphite-irondb

Using with graphite-api
-----------------------

In your graphite-api config file::

    irondb:
      urls:
        - http://irondb-host:port
    finders:
      - irondb.IronDBFinder

Using with graphite-web
-----------------------

In your graphite's ``local_settings.py``::

    STORAGE_FINDERS = (
        'irondb.IronDBFinder',
    )

    IRONDB_URLS = (
        'http://irondb-host:port'
    )

Where ``irondb-host:port`` is the location of the an IronDB node. If you have
a multi-node IronDB installation (likely), you should specify multiple URLS,
or place the IronDB installation behind a load balancer.

    # Graphite-API
    irondb:
      urls:
        - http://host1:port
        - http://host2:port

    # Graphite-web
    IRONDB_URLS = (
        'http://host1:port',
        'http://host2:port',
    )

Changelog
---------

* **0.0.1** (2016-10-31): initial version.
