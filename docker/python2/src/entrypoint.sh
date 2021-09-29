#!/usr/bin/env bash
echo "Starting nginx" && nginx
source /opt/graphite/bin/activate
[[ ! -d /graphite-irondb ]] && [[ ! -w /graphite-irondb ]] && exit 1
cd /graphite-irondb
[[ -d ./dist ]] && rm -rf ./dist && mkdir -p ./dist/py
[[ -d ./build ]] && rm -rf ./build
[[ -f ./graphite_irondb.egg-info ]] && rm -f ./graphite_irondb.egg-info
echo "Running setup.py"
python setup.py -q install || exit 1
export DJANGO_SETTINGS_MODULE='graphite.settings'
cd /graphite-irondb/test
#echo "Setup complete"
source testflatbuffer.sh || $(echo >&2 -e "Tests failed!" && exit 1)

if [[ $TEST_ONLY = false ]]
then 
    sed -i "s/@@CIRCONUS_API_KEY@@/$CIRCONUS_API_KEY/g" /opt/graphite/webapp/graphite/local_settings.py || echo >&2 -e "Failed to update CIRCONUS_API_KEY in local_settings.py"
    PYTHONPATH=/opt/graphite/webapp \
    /opt/graphite/bin/gunicorn wsgi \
    --workers=4 \
    --bind=127.0.0.1:8080 \
    --preload \
    --pythonpath=/opt/graphite/webapp/graphite
fi
