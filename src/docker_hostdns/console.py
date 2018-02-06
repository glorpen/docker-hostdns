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
from docker_hostdns.exceptions import StopException, ConfigException
import docker_hostdns
import os

try:
    import daemon
    _has_daemon = True
except ImportError:
    _has_daemon = False

def do_quit(*args):
    raise StopException()

class PidWriter(object):
    def __init__(self, pidpath):
        super(PidWriter, self).__init__()
        
        self.pidpath = pidpath
    
    def __enter__(self):
        if os.path.exists(self.pidpath):
            raise ConfigException("Pid file %r alread exists" % self.pidpath)
        
        with open(self.pidpath, "wt") as f:
            f.write("%d" % os.getpid())
    
    def __exit__(self, *args):
        os.unlink(self.pidpath)

def execute():
    p = argparse.ArgumentParser(description=docker_hostdns.__description__)
    p.add_argument('--zone', default="docker", help="Dns zone to update, defaults to \"docker\".")
    p.add_argument('--dns-server', default='127.0.0.1', action="store", help="Address of DNS server which will be updated, defaults to 127.0.0.1.")
    p.add_argument('--dns-key-secret', action="store", help="DNS Server key secret for use when updating zone. Use '-' to read from stdin.")
    p.add_argument('--dns-key-name', action="store", help="DNS Server key name for use when updating zone.")
    p.add_argument('--name', action="store", help="Name to differentiate between multiple instances inside same dns zone, defaults to current hostname.")
    
    if _has_daemon:
        p.add_argument('--daemonize', '-d', metavar="PIDFILE", action="store", default=None, help="Daemonize after start and store PID at given path.")
    
    p.add_argument('--verbose', '-v', default=0, action="count", help="Give more output. Option is additive, and can be used up to 3 times.")
    p.add_argument('--syslog', default=False, action="store_true", help="Enable logging to syslog.")
    
    conf = p.parse_args()
    
    keyring = None
    
    if conf.dns_key_name and conf.dns_key_secret:
        secret = conf.dns_key_secret
        
        if secret == "-":
            secret = sys.stdin.readline().strip()
        
        keyring={conf.dns_key_name: secret}
    
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
    
    dns_updater = NamedUpdater(conf.zone, conf.dns_server, keyring, conf.name)
    d = DockerHandler(dns_updater)
    
    dns_updater.setup()
    d.setup()
    
    def run():
        signal.signal(signal.SIGTERM, do_quit)
        signal.signal(signal.SIGINT, do_quit)
        logger = logging.getLogger('console')
        try:
            d.run()
        except Exception as e:
            logger.exception(e)
            raise e
    
    if _has_daemon and conf.daemonize:
        pid_writer = PidWriter(os.path.realpath(conf.daemonize))
        with daemon.DaemonContext(pidfile=pid_writer):
            run()
    else:
        run()
