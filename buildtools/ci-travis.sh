#!/bin/bash
set -e
if [ -z "$PYTHON_BIN" ]
then
    PYTHON_BIN="$(command -v python)"
fi

install_flatcc () {
    cd dist
    git clone https://github.com/dvidelabs/flatcc
    cmake flatcc \
        -DBUILD_SHARED_LIBS=on \
        -DCMAKE_BUILD_TYPE=Release \
        -DFLATCC_RTONLY=on \
        -DFLATCC_INSTALL=on \
        -DCMAKE_INSTALL_PREFIX:PATH=`pwd`
    make install
    cd ..
}

mkdir -p dist
install_flatcc
