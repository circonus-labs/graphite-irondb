#!/bin/bash
set -e
TEST=$(dirname $(readlink -f $0))
if [ -z "$PYTHON_BIN" ]
then
    PYTHON_BIN="$(command -v python)"
fi

cd dist
git clone https://github.com/graphite-project/graphite-web.git
cd graphite-web
PYTHONPATH=../../dist/py $PYTHON_BIN setup.py install --install-lib=../../dist/py/webapp --prefix=../../dist/py
cd ../../

DJANGO_SETTINGS_MODULE=graphite.settings $PYTHON_BIN $TEST/testparser.py