#!/usr/bin/env bash
service nginx start
source /opt/graphite/bin/activate
export DJANGO_SETTINGS_MODULE='graphite.settings'
PYTHONPATH="/opt/graphite/lib/:/opt/graphite/lib/python2.7/site-packages/:/opt/graphite/webapp/" \
    /opt/graphite/bin/gunicorn wsgi \
    --workers=4 \
    --bind=127.0.0.1:8080 \
    --preload \
    --pythonpath=/opt/graphite/webapp/graphite

