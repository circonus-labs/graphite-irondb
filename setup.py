# coding: utf-8
from setuptools import setup, find_packages, Extension

FLATCC_PREFIX='/opt/circonus'
FLATCC_CFLAGS=['-I%s/include'%FLATCC_PREFIX]
FLATCC_LDFLAGS=['-L%s/lib'%FLATCC_PREFIX,'-Wl,-rpath=%s/lib'%FLATCC_PREFIX,'-lflatccrt']

irondb_flatcc=Extension(
    'irondb_flatcc',
    sources=['irondb_flatcc/irondb_flatcc.c'],
    extra_compile_args=FLATCC_CFLAGS+['-fPIC','-O5','-Wno-strict-prototypes'],
    extra_link_args=FLATCC_LDFLAGS
)

setup(
    name='graphite-irondb',
    version='0.0.11',
    url='https://github.com/circonus-labs/graphite-irondb',
    license='BSD',
    author=u'Riley Berton',
    author_email='riley.berton@circonus.com',
    description=('A storage backend for graphite-web for using IronDB from Circonus'),
    long_description=open('README.md').read(),
    py_modules=('irondb',),
    ext_modules=[irondb_flatcc],
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
