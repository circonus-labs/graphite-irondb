FROM ubuntu:20.04 as distro
ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update \
     && apt-get install -y \
        git \
        nginx \
        python2-minimal \
        software-properties-common \
        gunicorn \
        curl \
        python3 \
        python3-distutils \
        python3-apt \
        python3-dev \
        python-dev \
        libcairo2-dev \
        libffi-dev \
        build-essential \
     && apt-add-repository universe && apt-get update && apt-get install -y python2.7 \
     && curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output get-pip.py \
     && python2 get-pip.py && python3 get-pip.py

FROM distro as graphite
SHELL ["/bin/bash", "-c"]
ENV GRAPHITE_ROOT /opt/graphite
ENV CONF_DIR /opt/graphite/conf
ENV STORAGE_DIR /opt/graphite/storage
RUN pip2 install virtualenv
RUN virtualenv /opt/graphite
ENV PYTHONPATH="/opt/graphite/lib/:/opt/graphite/webapp/"
RUN source /opt/graphite/bin/activate && pip2 install --no-binary=:all: https://github.com/graphite-project/whisper/tarball/master
RUN source /opt/graphite/bin/activate && pip2 install --no-binary=:all: https://github.com/graphite-project/carbon/tarball/master
RUN source /opt/graphite/bin/activate && pip2 install --no-binary=:all: https://github.com/graphite-project/graphite-web/tarball/master
RUN source /opt/graphite/bin/activate && pip2 install gunicorn
RUN git clone https://github.com/circonus-labs/graphite-irondb.git
RUN source /opt/graphite/bin/activate && cd /graphite-irondb && python2 setup.py install --pure-python
RUN source /opt/graphite/bin/activate && PYTHONPATH=$GRAPHITE_ROOT/webapp django-admin.py migrate --settings=graphite.settings
RUN chmod 777 /opt/graphite/storage/graphite.db
COPY src/graphite /etc/nginx/sites-available/graphite
COPY src/graphite-web.service /etc/systemd/system/graphite-web.service
COPY src/graphite-web.socket /etc/systemd/system/graphite-web.socket
RUN ln -s /etc/nginx/sites-available/graphite /etc/nginx/sites-enabled
RUN rm -f /etc/nginx/sites-enabled/default

EXPOSE 80
COPY src/local_settings.py /opt/graphite/webapp/graphite/local_settings.py
COPY src/entrypoint.sh /
ENTRYPOINT /entrypoint.sh