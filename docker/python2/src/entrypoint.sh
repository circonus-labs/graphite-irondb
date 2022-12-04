#!/usr/bin/env bash
export DJANGO_SETTINGS_MODULE='graphite.settings'
cd /usr/local/src/irondbgraphite/test
#echo "Setup complete"
source testflatbuffer.sh || $(echo >&2 -e "Tests failed!" && exit 1)

if [[ $TEST_ONLY = false ]]
then 
    PYTHONPATH="/opt/graphite/lib/:/opt/graphite/lib/python2.7/site-packages/:/opt/graphite/webapp/" \
    /opt/graphite/bin/gunicorn wsgi \
    --workers=4 \
    --bind=127.0.0.1:8080 \
    --preload \
    --pythonpath=/opt/graphite/webapp/graphite
fi
