#!/bin/bash
set -e
if [ -z "$PYTHON_BIN" ]
then
    PYTHON_BIN="$(command -v python3)"
fi

install_flatcc () {
    [[ -d ./dist ]] && rm -rf ./dist && mkdir -p ./dist/py
    [[ -d ./build ]] && rm -rf ./build
    cd ./dist
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

mkdir -p dist/py
install_flatcc
PYTHONPATH=dist/py $PYTHON_BIN setup.py install --user --install-lib=`pwd`/dist/py --with-flatcc=dist
PYTHONPATH=dist/py test/testflatbuffer.sh
