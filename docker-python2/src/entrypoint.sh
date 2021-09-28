source /opt/graphite/bin/activate
cd /graphite-irondb && python2 setup.py install
nginx
PYTHONPATH=/opt/graphite/webapp /opt/graphite/bin/gunicorn wsgi --workers=4 --bind=127.0.0.1:8080 --preload --pythonpath=/opt/graphite/webapp/graphite