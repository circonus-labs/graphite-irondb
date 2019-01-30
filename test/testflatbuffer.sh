#!/bin/bash
set -e
TEST=$(dirname $(readlink -f $0))
PYTHON=/opt/circonus/python27/bin/python

PYTHONPATH=. $PYTHON $TEST/testflatbuffer.py create_find_data irondb_find.bin 1024
PYTHONPATH=. $PYTHON $TEST/testflatbuffer.py create_get_data irondb_get.bin 1024

PYTHONPATH=. $PYTHON $TEST/testflatbuffer.py read_find_data irondb_find.bin -o > irondb_find_py.json
PYTHONPATH=. $PYTHON $TEST/testflatbuffer.py read_find_data irondb_find.bin -c -o > irondb_find_flatcc.json

PYTHONPATH=. $PYTHON $TEST/testflatbuffer.py read_get_data irondb_get.bin -o > irondb_get_py.json
PYTHONPATH=. $PYTHON $TEST/testflatbuffer.py read_get_data irondb_get.bin -c -o > irondb_get_flatcc.json

diff -qs irondb_find_py.json irondb_find_flatcc.json
diff -qs irondb_get_py.json irondb_get_flatcc.json
