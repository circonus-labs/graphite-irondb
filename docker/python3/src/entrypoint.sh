#!/usr/bin/env bash

spinner() {
    spin='-\|/'

    i=0
    while kill -0 $1 2>/dev/null
    do
        i=$(( (i+1) %4 ))
        printf "\r working: ${spin:$i:1}"
        sleep .1
    done
    echo ""
}

echo "Starting nginx" && nginx || exit 1
source /opt/graphite/bin/activate
echo "Cleaning up any pre-existing build artifacts"
[[ ! -d /graphite-irondb ]] && [[ ! -w /graphite-irondb ]] && exit 1
cd /graphite-irondb
[[ -d ./dist ]] && rm -rf ./dist && mkdir -p ./dist/py
[[ -d ./build ]] && rm -rf ./build
[[ -f ./graphite_irondb.egg-info ]] && rm -f ./graphite_irondb.egg-info
echo "Running setup"
python3 setup.py -q install > /dev/null 2>&1 &
pid=$!
spinner $pid
export DJANGO_SETTINGS_MODULE='graphite.settings'
cd /graphite-irondb/test
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
