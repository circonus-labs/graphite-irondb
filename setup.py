# coding: utf-8
from setuptools import setup

setup(
    name='graphite-irondb',
    version='0.0.6',
    url='https://github.com/circonus-labs/graphite-irondb',
    license='BSD',
    author=u'Riley Berton',
    author_email='riley.berton@circonus.com',
    description=('A storage backend for graphite-web for using IronDB from Circonus'),
    long_description=open('README.md').read(),
    py_modules=('irondb',),
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
