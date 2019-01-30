#!/bin/bash
set -e
TEST=$(dirname $(readlink -f $0))
if [ -z "$PYTHON_BIN" ]
then
    PYTHON_BIN="$(command -v python)"
fi
testflatbuffer () {
    $PYTHON_BIN $TEST/testflatbuffer.py "$@"
}

testflatbuffer create_find_data irondb_find.bin 1024
testflatbuffer create_get_data irondb_get.bin 1024

testflatbuffer read_find_data irondb_find.bin -o > irondb_find_py.json
testflatbuffer read_find_data irondb_find.bin -c -o > irondb_find_flatcc.json

testflatbuffer read_get_data irondb_get.bin -o > irondb_get_py.json
testflatbuffer read_get_data irondb_get.bin -c -o > irondb_get_flatcc.json

diff -qs irondb_find_py.json irondb_find_flatcc.json
diff -qs irondb_get_py.json irondb_get_flatcc.json
