'''
Created on 31.03.2017

@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
'''
import sys
import signal
import logging
import argparse
from logging.handlers import SysLogHandler
from docker_hostdns.hostdns import NamedUpdater, DockerHandler
from docker_hostdns.exceptions import StopException

try:
    import daemon
    _has_daemon = True
except ImportError:
    _has_daemon = False

p = argparse.ArgumentParser()
p.add_argument('--domain', default="docker")
p.add_argument('--dns-server', default='127.0.0.1', action="store", help="DNS server to send updates to")
p.add_argument('--dns-key-secret', action="store", help="DNS Server key secret for use when updating zone. Use '-' to read from stdin.")
p.add_argument('--dns-key-name', action="store", help="DNS Server key name for use when updating zone")

if _has_daemon:
    p.add_argument('--daemonize', '-d', action="store_true", default=False)

p.add_argument('--verbose', '-v', default=0, action="count")
p.add_argument('--syslog', default=False, action="store_true")

conf = p.parse_args()

keyring = None

if conf.dns_key_name and conf.dns_key_secret:
    secret = conf.dns_key_secret
    
    if secret == "-":
        secret = sys.stdin.readline().strip()
    
    keyring={conf.dns_key_name: secret}

dns_updater = NamedUpdater(conf.domain, conf.dns_server, keyring)
d = DockerHandler(dns_updater)

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

def do_quit(*args):
    raise StopException()

def run():
    signal.signal(signal.SIGTERM, do_quit)
    signal.signal(signal.SIGINT, do_quit)
    d.run()

if _has_daemon and conf.daemonize:
    with daemon.DaemonContext():
        run()
else:
    run()
