'''
Created on 31.03.2017

@author: glorpen
'''
import argparse
from docker_hostdns.hostdns import NamedUpdater, DockerDnsmasq
import logging
from logging.handlers import SysLogHandler
import daemon

p = argparse.ArgumentParser()
p.add_argument('--domain', default="docker")
p.add_argument('--docker-url', default="unix://var/run/docker.sock")
p.add_argument('--dns-server', default='127.0.0.1', action="store", help="DNS server to send updates to")

p.add_argument('--daemonize', '-d', action="store_true", default=False)
p.add_argument('--verbose', '-v', default=0, action="count")
p.add_argument('--syslog', default=False, action="store_true")

conf = p.parse_args()

dns_updater = NamedUpdater(conf.domain, conf.dns_server)
d = DockerDnsmasq(conf.docker_url, dns_updater)

levels = [
    logging.ERROR,
    logging.WARNING,
    logging.INFO,
    logging.DEBUG
]

handlers = None

if conf.syslog:
    h = SysLogHandler(facility=SysLogHandler.LOG_DAEMON, address='/dev/log')
    formatter = logging.Formatter(p.prog+' [%(name)s] %(message)s', '%b %e %H:%M:%S')
    h.setFormatter(formatter)
    handlers = [h]

logging.basicConfig(level=levels[min(conf.verbose, len(levels)-1)], handlers=handlers)

dns_updater.setup()
d.setup()

if conf.daemonize:
    with daemon.DaemonContext():
        d.run()
else:
    d.run()
