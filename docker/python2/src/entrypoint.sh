#!/usr/bin/env bash
echo "Starting nginx" && nginx
source /opt/graphite/bin/activate
[[ ! -d /graphite-irondb ]] && [[ ! -w /graphite-irondb ]] && exit 1
cd /graphite-irondb
[[ -d ./dist ]] && rm -rf ./dist && mkdir -p ./dist/py
[[ -d ./build ]] && rm -rf ./build
[[ -f ./graphite_irondb.egg-info ]] && rm -f ./graphite_irondb.egg-info
echo "Running setup.py"
python2 setup.py -q install || exit 1
export DJANGO_SETTINGS_MODULE='graphite.settings'
cd /graphite-irondb/test
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
