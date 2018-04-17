# coding: utf-8
import sys
from setuptools import setup, find_packages, Extension

FLATCC_PREFIX='/opt/circonus'

def build_ext(argv, setup_args):
    pure_python = False
    with_flatcc = FLATCC_PREFIX    
    if '--pure-python' in argv:
        pure_python = True
        argv.remove('--pure-python')
    for arg in argv:
        if arg.startswith('--with-flatcc='):
            assert pure_python == False, 'Cannot combine options --pure-python and --with-flatcc'
            with_flatcc = arg.split('=')[1]
            assert with_flatcc != '', '--with-flatcc option cannot have empty path'
            argv.remove(arg)
            break
    if not pure_python:
        setup_args['ext_modules']=[Extension(
            'irondb_flatcc',
            sources=['irondb_flatcc/irondb_flatcc.c'],
            extra_compile_args=['-I%s/include'%with_flatcc,'-fPIC','-O5','-Wno-strict-prototypes'],
            extra_link_args=['-L%s/lib'%with_flatcc,'-Wl,-rpath=%s/lib'%with_flatcc,'-lflatccrt']
        )]

setup_args=dict(
    name='graphite-irondb',
    version='0.0.13',
    url='https://github.com/circonus-labs/graphite-irondb',
    license='BSD',
    author=u'Riley Berton',
    author_email='riley.berton@circonus.com',
    description=('A storage backend for graphite-web for using IronDB from Circonus'),
    long_description=open('README.md').read(),
    py_modules=('irondb','irondb_flatbuf'),
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    classifiers=(
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Topic :: System :: Monitoring',
    ),
    install_requires=(
        'requests',
    )
)

graphite_irondb_help = '''
Graphite IRONdb options:
 --pure-python          Use pure Python code for FlatBuffers
 --with-flatcc=PREFIX   Path prefix for flatcc library
'''

if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print graphite_irondb_help
    else:
        build_ext(sys.argv, setup_args)
    setup(**setup_args)
