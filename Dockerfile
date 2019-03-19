FROM python:3.6.6-alpine as base

LABEL maintainer="Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>"

FROM base as build

COPY README.rst CHANGES.rst setup.py /srv/
COPY src /srv/src

RUN pip install /srv \
    && rm -rf /root/.cache \
    && find /usr/local -depth \
    \( \
      \( -type d -a \( -name test -o -name tests \) \) \
      -o \
      \( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
    \) -exec rm -rf '{}' +;

FROM base

COPY --from=build /usr/local/ /usr/local/

ADD docker/entrypoint.py /usr/local/bin/docker-entrypoint

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
