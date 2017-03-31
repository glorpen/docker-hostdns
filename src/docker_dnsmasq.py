'''
Created on 29.03.2017

@author: glorpen
'''

from docker import APIClient
import argparse
import daemon
import os
from logging.handlers import SysLogHandler
import logging

import dns.update
import dns.query
import dns.tsigkeyring

"""
import sys

sys.exit()

keyring = dns.tsigkeyring.from_text({
    'keyname.' : 'NjHwPsMKjdN++dOfE5iAiQ=='
})

#update = dns.update.Update('docker.', keyring=keyring)
update = dns.update.Update('docker.')
#update.replace('host', 300, 'A', "10.0.0.123")
#update.add('host2', 300, 'A', "10.0.0.123")
#update.delete('host2', 'A', "10.0.0.123")
#update.add('_container', 0, 'TXT', "host")
#update.add('_container', 0, 'TXT', "host2")
#update.add('.', 0, 'TXT', "host=host2")

response = dns.query.tcp(update, '127.0.0.1', timeout=10)

sys.exit()
"""

class AppException(Exception):
    pass

class ConnectionException(AppException):
    pass

class ConfigException(AppException):
    pass

class NamedUpdater(object):
    def __init__(self, domain, dns_server):
        super(NamedUpdater, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.domain = domain
        self.dns_server = dns_server
    
    def load_records(self):
        qname = dns.name.from_text("_container.%s" % self.domain)
        q = dns.message.make_query(qname, dns.rdatatype.TXT)
        
        r = dns.query.udp(q, self.dns_server)
        
        ret = []
        if r.answer:
            ns_rrset = r.find_rrset(r.answer, qname, dns.rdataclass.IN, dns.rdatatype.TXT)
            
            for rr in ns_rrset:
                for i in rr.strings:
                    ret.append(i)
    
        self.hosts = set(ret)
        
    def setup(self):
        self.load_records()
    
    def add_host(self, host, ip):
        update = dns.update.Update('%s.' % self.domain)
        
        update.add(host, 1, "A", ip)
        update.add("*.%s" % host, 1, "A", ip)
        update.add("_container", 1, "TXT", host)
        
        response = dns.query.tcp(update, self.dns_server, timeout=2)
        #print(response)
    
    def remove_host(self, host):
        update = dns.update.Update('%s.' % self.domain)
        
        update.delete(host, 'A')
        update.delete("*.%s" % host, 'A')
        update.delete("_container", 'TXT', host)
        
        response = dns.query.tcp(update, self.dns_server, timeout=2)
        #print(response)

class DockerDnsmasq(object):
    
    client = None
    
    def __init__(self, docker_url, dnsupdater):
        super(DockerDnsmasq, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.docker_url = docker_url
        
        self.dnsupdater = dnsupdater
        self._hosts_cache = {}
    
    def setup(self):
        try:
            client = APIClient(base_url=self.docker_url)
            client.ping()
        except Exception:
            raise ConnectionException('Error communicating with docker socket %s. Stopping.', self.docker_url)
        
        self.logger.info("Connected to %r", self.docker_url)
        self.client = client
    
    def on_disconnect(self, container_id):
        name = self._hosts_cache[container_id]
        self.logger.info("Removing entry %r as container %r disconnected", name, container_id)
        del self._hosts_cache[container_id]
            
        self.dnsupdater.remove_host(name)
    
    def on_connect(self, name, ip, container_id):
        name = name.replace('/', '').replace('_', '-')
        self.logger.info("Adding new entry %r:%r for container %r", name, ip, container_id)
        self._hosts_cache[container_id] = name
        self.dnsupdater.add_host(name, ip)
        
    def handle_event(self, event):
        if event["Type"] == "network":
            if event["Action"] == "connect":
                container_id = event["Actor"]["Attributes"]["container"]
                self.logger.debug("Handling connect event for container %r", container_id)
                d = self.client.inspect_container(container_id)
                name = d["Name"]
                network_mode = d["HostConfig"]["NetworkMode"]
                ip = d["NetworkSettings"]["Networks"][network_mode]["IPAddress"]
                
                name = d["Config"]["Labels"].get("pl.glorpen.hostname", name)
                
                self.on_connect(name, ip, container_id)
            if event["Action"] == "disconnect":
                container_id = event["Actor"]["Attributes"]["container"]
                self.logger.debug("Handling disconnect event for container %r", container_id)
                self.on_disconnect(container_id)
    
    def run(self):
        events = self.client.events(decode=True)
        
        while True:
            try:
                event = next(events)
            except Exception:
                self.logger.info("Docker connection broken - exitting")
                return
            self.handle_event(event)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--domain', default="docker")
    p.add_argument('--docker-url', default="unix://var/run/docker.sock")
    p.add_argument('--dns-server', default='127.0.0.1', action="store", help="DNS server to send updates to")
    
    p.add_argument('--daemonize', '-d', action="store_true", default=False)
    p.add_argument('--verbose', '-v', default=0, action="count")
    p.add_argument('--syslog', default=False, action="store_true")
    
    conf = p.parse_args()
    
    dnsmasq = NamedUpdater(conf.domain, conf.dns_server)
    d = DockerDnsmasq(conf.docker_url, dnsupdater = dnsmasq)
    
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
    
    dnsmasq.setup()
    d.setup()
    
    if conf.daemonize:
        with daemon.DaemonContext():
            d.run()
    else:
        d.run()
