FROM ubuntu:20.04 as distro
ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update \
     && apt-get install -y \
        git \
        nginx \
        python2-minimal \
        software-properties-common \
        python-dev \
        libcairo2-dev \
        libffi-dev \
        build-essential \
        curl \
        cmake \
        ninja-build \
     && apt-add-repository universe && apt-get update && apt-get install -y python2.7 \
     && curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output get-pip.py \
     && python2 get-pip.py

FROM distro as flatcc
RUN git clone https://github.com/dvidelabs/flatcc.git
RUN cd flatcc && scripts/build.sh
RUN ln -s /flatcc /opt/circonus

FROM flatcc as graphite
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