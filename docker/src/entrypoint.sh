source /opt/graphite/bin/activate
#cd /graphite-irondb
#python setup.py install --pure-python
#/usr/bin/gunicorn wsgi --pythonpath=/opt/graphite/webapp/graphite --bind 0.0.0.0:8080
# /opt/graphite/bin/gunicorn wsgi --pythonpath=/opt/graphite/webapp/graphite --bind 0.0.0.0:8080
source /opt/graphite/bin/activate && cd /graphite-irondb && python2 setup.py install --pure-python
nginx
PYTHONPATH=/opt/graphite/webapp /opt/graphite/bin/gunicorn wsgi --workers=4 --bind=127.0.0.1:8080 --preload --pythonpath=/opt/graphite/webapp/graphite

# while :
# do
# 	echo "Press [CTRL+C] to stop.."
# 	sleep 1
# done