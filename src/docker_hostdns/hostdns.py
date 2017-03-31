'''
Created on 29.03.2017

@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
'''

import re
import docker
import logging
import dns.query
import dns.update
import dns.tsigkeyring
from docker_hostdns.exceptions import ConnectionException, DnsException,\
    StopException

class NamedUpdater(object):
    
    keyring = None
    
    def __init__(self, zone, dns_server, keyring=None):
        super(NamedUpdater, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.zone = zone
        self.dns_server = dns_server
        
        if keyring:
            self.keyring = dns.tsigkeyring.from_text(keyring)
    
    def load_records(self):
        qname = dns.name.from_text("_container.%s" % self.zone)
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
    
    def set_hosts(self, hosts):
        current_hosts = []
        for host, (ipv4, ipv6) in hosts.items():
            current_hosts.append(host)
            if host not in self.hosts:
                self.add_host(host, ipv4, ipv6)
        
        for old_host in self.hosts.difference(current_hosts):
            self.remove_host(old_host)
    
    def add_host(self, host, ipv4=None, ipv6=None):
        self.logger.debug("Adding host %r", host)
        update = dns.update.Update('%s.' % self.zone, keyring=self.keyring)
        
        if ipv4:
            update.add(host, 1, "A", ipv4)
            update.add("*.%s" % host, 1, "A", ipv4)
        
        if ipv6:
            update.add(host, 1, "AAAA", ipv6)
            update.add("*.%s" % host, 1, "AAAA", ipv6)
        
        update.add("_container", 1, "TXT", host)
        
        self._update(update)
    
    def _update(self, update):
        response = dns.query.tcp(update, self.dns_server, timeout=2)
        
        rcode = response.rcode()
        if rcode != dns.rcode.NOERROR:
            raise DnsException("Adding host failed with %s" % dns.rcode.to_text(rcode))
    
    def remove_host(self, host):
        self.logger.debug("Removing host %r", host)
        update = dns.update.Update('%s.' % self.zone, keyring=self.keyring)
        
        update.delete(host, 'A')
        update.delete("*.%s" % host, 'A')
        
        update.delete(host, 'AAAA')
        update.delete("*.%s" % host, 'AAAA')
        
        update.delete("_container", 'TXT', host)
        
        self._update(update)

class ContainerInfo(object):
    ipv4 = None
    ipv6 = None
    id = None
    name = None
    
    re_name = re_chars = re.compile('[^a-zA-Z0-9_-]+')
    
    def __init__(self, **kwargs):
        super(ContainerInfo, self).__init__()
        
        self.__dict__.update(kwargs)
    
    @classmethod
    def from_container(cls, container):
        d = container.attrs
        
        id_ = d["Id"]
        name = d["Name"]
        network_mode = d["HostConfig"]["NetworkMode"]
        ipv4 = d["NetworkSettings"]["Networks"][network_mode]["IPAddress"] or None
        ipv6 = d["NetworkSettings"]["Networks"][network_mode]["GlobalIPv6Address"] or None
        name = d["Config"]["Labels"].get("pl.glorpen.hostname", name)
        
        name = cls.re_name.sub("-", name).strip("-")
        
        return cls(id=id_, name=name, ipv4=ipv4, ipv6=ipv6)

class DockerHandler(object):
    
    client = None
    
    def __init__(self, dns_updater):
        super(DockerHandler, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.dns_updater = dns_updater
        self._hosts_cache = {}
    
    def setup(self):
        try:
            client = docker.from_env()
            client.ping()
        except Exception:
            raise ConnectionException('Error communicating with docker.')
        
        self.logger.info("Connected to docker")
        self.client = client
        
        self.load_containers()
    
    def _deduplicate_container_name(self, name):
        cnt = list(self._hosts_cache.values()).count(name)
        if cnt > 0:
            old_name = name
            name = "%s-%d" % (old_name, cnt)
            self.logger.warning('Duplicated host %r, renamed to %r', old_name, name)
        
        return name
    
    def load_containers(self):
        known_hosts = {}
        
        for container in self.client.containers.list(filters={"status":"running"}):
            info = ContainerInfo.from_container(container)
            
            unique_name = self._deduplicate_container_name(info.name)
            self._hosts_cache[info.id] = unique_name
            known_hosts[unique_name] = (info.ipv4, info.ipv6)
        
        self.dns_updater.set_hosts(known_hosts)
    
    def on_disconnect(self, container_id):
        name = self._hosts_cache[container_id]
        self.logger.info("Removing entry %r as container %r disconnected", name, container_id)
        del self._hosts_cache[container_id]
            
        self.dns_updater.remove_host(name)
    
    def on_connect(self, container_id, name, ipv4, ipv6):
        unique_name = self._deduplicate_container_name(name)
        self.logger.info("Adding new entry %r:[ipv4:%r, ipv6:%r] for container %r", unique_name, ipv4, ipv6, container_id)
        self._hosts_cache[container_id] = unique_name
        self.dns_updater.add_host(unique_name, ipv4, ipv6)
        
    def handle_event(self, event):
        if event["Type"] == "network":
            if event["Action"] == "connect":
                container_id = event["Actor"]["Attributes"]["container"]
                self.logger.debug("Handling connect event for container %r", container_id)
                info = ContainerInfo.from_container(self.client.containers.get(container_id))
                self.on_connect(container_id, info.name, info.ipv4, info.ipv6)
            
            if event["Action"] == "disconnect":
                container_id = event["Actor"]["Attributes"]["container"]
                self.logger.debug("Handling disconnect event for container %r", container_id)
                self.on_disconnect(container_id)
    
    def run(self):
        events = self.client.events(decode=True)
        
        while True:
            try:
                event = next(events)
            except StopException:
                self.logger.info("Exitting")
                return
            except Exception:
                self.logger.info("Docker connection broken - exitting")
                return
            
            self.handle_event(event)
