nginx
source /opt/graphite/bin/activate
cd /graphite-irondb && python3 setup.py install
# PYTHONPATH=/opt/graphite/webapp /opt/graphite/bin/gunicorn wsgi --workers=4 --bind=127.0.0.1:8080 --preload --pythonpath=/opt/graphite/webapp/graphite
export DJANGO_SETTINGS_MODULE='graphite.settings'
cd /graphite-irondb/test
./testflatbuffer.sh

while :
do
	echo "Press [CTRL+C] to stop.."
	sleep 1
done