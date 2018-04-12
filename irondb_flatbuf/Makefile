# TODO FIXME
all:
	gcc -I/opt/circonus/include -I/opt/circonus/include/flatbuffers irondb_flatbuf.c -g -fPIC -shared -o ../irondb_flatbuf.so `pkg-config python --cflags` -L/opt/circonus/lib -Wl,-rpath=/opt/circonus/lib -lflatccrt
