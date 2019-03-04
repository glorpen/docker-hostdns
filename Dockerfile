FROM python:3.6.6-alpine

LABEL maintainer="Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>"

ADD docker/entrypoint.py /usr/local/bin/docker-entrypoint

ARG HOSTDNS_VERSION=

ADD dist/docker_hostdns-${HOSTDNS_VERSION}-py3-none-any.whl /usr/local/share/
RUN pip install /usr/local/share/docker_hostdns-${HOSTDNS_VERSION}-py3-none-any.whl \
    && rm -rf /root/.cache

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
