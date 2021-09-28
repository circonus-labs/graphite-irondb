FROM ubuntu:20.04 as distro
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
RUN git clone https://github.com/dvidelabs/flatcc.git
RUN cd flatcc && scripts/build.sh
RUN ln -s /flatcc /opt/circonus

FROM flatcc as graphite
SHELL ["/bin/bash", "-c"]
ENV GRAPHITE_ROOT /opt/graphite
ENV CONF_DIR /opt/graphite/conf
ENV STORAGE_DIR /opt/graphite/storage
RUN pip install virtualenv
RUN virtualenv /opt/graphite
ENV PYTHONPATH="/opt/graphite/lib/:/opt/graphite/webapp/"
RUN source /opt/graphite/bin/activate && pip install --no-binary=:all: https://github.com/graphite-project/whisper/tarball/master
#RUN source /opt/graphite/bin/activate && pip install --no-binary=:all: https://github.com/graphite-project/carbon/tarball/master
RUN source /opt/graphite/bin/activate && pip install --no-binary=:all: https://github.com/graphite-project/graphite-web/tarball/master
RUN curl -L https://github.com/graphite-project/graphite-web/tarball/master --output /graphite-web.tar.gz 
RUN tar xf /graphite-web.tar.gz
RUN rm -rf /opt/graphite/webapp/graphite && mv /graphite-p*/webapp/graphite /opt/graphite/webapp/graphite
RUN source /opt/graphite/bin/activate && pip install gunicorn
RUN mkdir -p /opt/graphite/lib/python3.8/storage/log/webapp/ 
#&& touch /opt/graphite/lib/python3.8/storage/log/webapp/info.log
RUN source /opt/graphite/bin/activate && /opt/graphite/bin/django-admin.py migrate --settings=graphite.settings
#RUN chmod 777 /opt/graphite/storage/graphite.db
COPY src/graphite /etc/nginx/sites-available/graphite
COPY src/graphite-web.service /etc/systemd/system/graphite-web.service
COPY src/graphite-web.socket /etc/systemd/system/graphite-web.socket
RUN ln -s /etc/nginx/sites-available/graphite /etc/nginx/sites-enabled
RUN rm -f /etc/nginx/sites-enabled/default

EXPOSE 80
COPY src/local_settings.py /opt/graphite/webapp/graphite/local_settings.py
COPY src/entrypoint.sh /
ENTRYPOINT /entrypoint.sh