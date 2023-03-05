FROM ubuntu:22.04 as distro
ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update \
     && apt-get install -y \
        git \
        nginx \
        python2-minimal \
        software-properties-common \
        python2-dev \
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
RUN git clone https://github.com/dvidelabs/flatcc.git /opt/flatcc \
    && cd /opt/flatcc && scripts/build.sh \
    && ln -s /opt/flatcc /opt/circonus

FROM flatcc as graphite
SHELL ["/bin/bash", "-c"]
ENV GRAPHITE_ROOT /opt/graphite
ENV CONF_DIR /opt/graphite/conf
ENV STORAGE_DIR /opt/graphite/storage
ENV PYTHONPATH="/opt/graphite/lib/:/opt/graphite/lib/python2.7/site-packages/:/opt/graphite/webapp/"

ARG graphite_version=1.1.10
ARG irondbgraphite_repo="--branch python3-upd https://github.com/deniszh/graphite-irondb"
#ARG irondbgraphite_repo="https://github.com/circonus-labs/graphite-irondb"

RUN pip2 install incremental==17.5.0 twisted==20.3.0 django==1.11.29 \
   && git clone ${irondbgraphite_repo} /usr/local/src/irondbgraphite \
   && cd /usr/local/src/irondbgraphite \
   && pip2 install future requests==2.27.1 flatbuffers \
   && python2 ./setup.py install --with-flatcc=/opt/circonus \
   && pip2 install --no-binary=:all: https://github.com/graphite-project/whisper/tarball/master \
   && pip2 install --no-binary=:all: https://github.com/graphite-project/carbon/tarball/master \
   && git clone -b ${graphite_version} --depth 1 https://github.com/graphite-project/graphite-web.git /usr/local/src/graphite-web \
   && cd /usr/local/src/graphite-web \
   && pip2 install -r requirements.txt && python2 ./setup.py install \
   && pip2 install gunicorn \
   && mkdir -p /usr/lib/python2.7/site-packages/storage/log/webapp/ \
   && mkdir -p /opt/graphite/storage/log/ \
   && ln -s /usr/lib/python2.7/site-packages/storage/log/webapp/ /opt/graphite/storage/log/webapp/ \
   && django-admin.py migrate --settings=graphite.settings \
   && django-admin.py collectstatic --settings=graphite.settings

RUN chmod 777 /opt/graphite/storage/graphite.db
COPY src/graphite /etc/nginx/sites-available/graphite
RUN ln -s /etc/nginx/sites-available/graphite /etc/nginx/sites-enabled \
   && rm -f /etc/nginx/sites-enabled/default
COPY src/local_settings.py /opt/graphite/webapp/graphite/local_settings.py
COPY src/entrypoint.sh /

EXPOSE 80

ENTRYPOINT /entrypoint.sh