#!/usr/bin/env bash
service nginx start
export DJANGO_SETTINGS_MODULE='graphite.settings'
PYTHONPATH="/opt/graphite/lib/:/usr/local/lib/python2.7/dist-packages/:/usr/local/lib/python2.7/site-packages/:/opt/graphite/webapp/" \
    /usr/local/bin/gunicorn wsgi \
	--chdir /opt/graphite/webapp/graphite \
    --workers=4 \
    --bind=127.0.0.1:8080 \
    --preload
