#!/bin/bash
TEST="$_"
set -Eeuo pipefail
trap cleanup SIGINT SIGTERM ERR EXIT
# script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)
# TEST=$(dirname $(readlink -f $0))
PYTHON_BIN="$(command -v python)"
[[ -z $PYTHON_BIN ]] && die "Unable to find Python."

testflatbuffer () {
    $PYTHON_BIN $TEST/testflatbuffer.py "$@"
}

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  rm *.json
  rm *.bin
  # script cleanup here
}

msg() {
  echo >&2 -e "${1-}"
}

die() {
  local msg=$1
  local code=${2-1} # default exit status 1
  msg "$msg"
  exit $code
}

cd $TEST
rm *.json
rm *.bin

testflatbuffer create_find_data irondb_find.bin 1024 || die ""
testflatbuffer create_get_data irondb_get.bin 1024 || die ""

testflatbuffer read_find_data irondb_find.bin -o > irondb_find_py.json || die ""
testflatbuffer read_find_data irondb_find.bin -c -o > irondb_find_flatcc.json || die ""

testflatbuffer read_get_data irondb_get.bin -o > irondb_get_py.json || die ""
testflatbuffer read_get_data irondb_get.bin -c -o > irondb_get_flatcc.json || die ""

diff -qs irondb_find_py.json irondb_find_flatcc.json | grep identical \
 || die "Test Failed: irondb_find_py.json & irondb_find_flatcc.json differ"

diff -qs irondb_get_py.json irondb_get_flatcc.json | grep identical \
 || die "Test Failed: irondb_get_py.json & irondb_get_flatcc.json differ"
msg "Tests passed!"
