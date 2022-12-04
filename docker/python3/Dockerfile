FROM ubuntu:22.04 as distro
ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update \
     && apt-get install -y \
        git \
        nginx \
        software-properties-common \
        gunicorn \
        curl \
        python3 \
        python3-distutils \
        python3-apt \
        python3-dev \
        python3-pip \
        libcairo2-dev \
        libffi-dev \
        build-essential \
        cmake \
        ninja-build

FROM distro as flatcc
RUN git clone https://github.com/dvidelabs/flatcc.git /opt/flatcc \
    && cd /opt/flatcc && scripts/build.sh \
    && ln -s /opt/flatcc /opt/circonus

FROM flatcc as graphite
SHELL ["/bin/bash", "-c"]
ENV GRAPHITE_ROOT /opt/graphite
ENV CONF_DIR /opt/graphite/conf
ENV STORAGE_DIR /opt/graphite/storage
ENV PYTHONPATH="/opt/graphite/lib/:/opt/graphite/lib/python3.10/site-packages/:/opt/graphite/webapp/"

ARG graphite_version=1.1.10
RUN git clone --branch python3-upd https://github.com/deniszh/graphite-irondb /usr/local/src/irondbgraphite \
    && cd /usr/local/src/irondbgraphite \
    && pip3 install future requests flatbuffers \
    && python3 ./setup.py install --with-flatcc=/opt/circonus \
    && pip3 install --no-binary=:all: https://github.com/graphite-project/whisper/tarball/master \
    && pip3 install --no-binary=:all: https://github.com/graphite-project/carbon/tarball/master \
    && git clone -b ${graphite_version} --depth 1 https://github.com/graphite-project/graphite-web.git /usr/local/src/graphite-web \
    && cd /usr/local/src/graphite-web \
    && pip3 install -r requirements.txt && python3 ./setup.py install \
    && pip3 install gunicorn \
    && mkdir -p /usr/local/lib/python3.10/site-packages/storage/log/webapp/ \
    && mkdir -p /opt/graphite/storage/log/ \
    && ln -s /usr/local/lib/python3.10/site-packages/storage/log/webapp/ /opt/graphite/storage/log/webapp/ \
    && django-admin.py migrate --settings=graphite.settings \
    && mkdir -p /usr/local/lib/python3.10/site-packages/graphite_web-1.1.10-py3.10.egg/content \
    && django-admin.py collectstatic --settings=graphite.settings

COPY src/graphite /etc/nginx/sites-available/graphite
RUN ln -s /etc/nginx/sites-available/graphite /etc/nginx/sites-enabled \
    && rm -f /etc/nginx/sites-enabled/default
COPY src/local_settings.py /usr/local/lib/python3.10/site-packages/graphite_web-1.1.10-py3.10.egg/graphite/local_settings.py
COPY src/entrypoint.sh /

EXPOSE 80

ENTRYPOINT /entrypoint.sh