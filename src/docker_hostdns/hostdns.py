'''
Created on 29.03.2017

@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
'''

import re
import docker
import logging
import socket
import dns.query
import dns.update
import dns.tsigkeyring
from docker_hostdns.exceptions import ConnectionException, DnsException,\
    StopException

def _as_str(s):
    if isinstance(s, bytes):
        return s.decode()
    return s

class NamedUpdater(object):
    
    keyring = None
    
    def __init__(self, zone, dns_server, keyring=None, instance_name=None):
        super(NamedUpdater, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.zone = zone
        self.dns_server = dns_server
        self.hosts = set()
        
        self._dns_zone = dns.name.from_text(self.zone)
        
        if not instance_name:
            instance_name = socket.gethostname()
        
        self._dns_txt_record = dns.name.from_text("_container_%s" % instance_name, self._dns_zone)
        
        if keyring:
            self.keyring = dns.tsigkeyring.from_text(keyring)
    
    def load_records(self):
        q = dns.message.make_query(self._dns_txt_record, dns.rdatatype.TXT)
        
        r = dns.query.udp(q, self.dns_server)
        
        ret = []
        if r.answer:
            ns_rrset = r.find_rrset(r.answer, self._dns_txt_record, dns.rdataclass.IN, dns.rdatatype.TXT)
            
            for rr in ns_rrset:
                for i in rr.strings:
                    ret.append(_as_str(i))
    
        self.hosts = set(ret)
        
    def setup(self):
        self.load_records()
    
    def set_hosts(self, hosts):
        current_hosts = []
        for host, (ipv4s, ipv6s) in hosts.items():
            current_hosts.append(host)
            if host not in self.hosts:
                self.add_host(host, ipv4s, ipv6s)
        
        for old_host in self.hosts.difference(current_hosts):
            self.remove_host(old_host)
    
    def add_host(self, host, ipv4s=None, ipv6s=None):
        self.logger.debug("Adding host %r", host)
        update = dns.update.Update(self._dns_zone, keyring=self.keyring)
        
        if ipv4s or ipv6s:
            dns_name_single = dns.name.from_text(host, self._dns_zone)
            dns_name_multi = dns.name.from_text("*.%s" % host, self._dns_zone)
        
        if ipv4s:
            for ipv4 in ipv4s:
                update.add(dns_name_single, 1, dns.rdatatype.A, ipv4)
                update.add(dns_name_multi, 1, dns.rdatatype.A, ipv4)
        
        if ipv6s:
            for ipv6 in ipv6s:
                update.add(dns_name_single, 1, dns.rdatatype.AAAA, ipv6)
                update.add(dns_name_multi, 1, dns.rdatatype.AAAA, ipv6)
        
        update.add(self._dns_txt_record, 1, dns.rdatatype.TXT, host)
        
        self._update(update)
        self.hosts.add(host)
    
    def _update(self, update):
        response = dns.query.tcp(update, self.dns_server, timeout=2)
        
        rcode = response.rcode()
        if rcode != dns.rcode.NOERROR:
            raise DnsException("Adding host failed with %s" % dns.rcode.to_text(rcode))
    
    def remove_host(self, host):
        self.logger.debug("Removing host %r", host)
        update = dns.update.Update(self._dns_zone, keyring=self.keyring)
        
        dns_name_single = dns.name.from_text(host, self._dns_zone)
        dns_name_multi = dns.name.from_text("*.%s" % host, self._dns_zone)
        
        update.delete(dns_name_single, dns.rdatatype.A)
        update.delete(dns_name_multi, dns.rdatatype.A)
        
        update.delete(dns_name_single, dns.rdatatype.AAAA)
        update.delete(dns_name_multi, dns.rdatatype.AAAA)
        
        update.delete(self._dns_txt_record, dns.rdatatype.TXT, host)
        
        self._update(update)
        
        if host in self.hosts:
            self.hosts.remove(host)

class ContainerInfo(object):
    ipv4s = None
    ipv6s = None
    id = None
    name = None
    
    re_name = re.compile('[^a-zA-Z0-9-.]+')
    
    def __init__(self, **kwargs):
        super(ContainerInfo, self).__init__()
        
        self.__dict__.update(kwargs)
    
    @classmethod
    def from_container(cls, container):
        d = container.attrs
        
        id_ = d["Id"]
        name = d["Name"]
        
        ipv4s = []
        ipv6s = []
        
        for network in d["NetworkSettings"]["Networks"].values():
            if network["IPAddress"]:
                ipv4s.append(network["IPAddress"])
            if network["GlobalIPv6Address"]:
                ipv6s.append(network["GlobalIPv6Address"])
        
        name = d["Config"]["Labels"].get("pl.glorpen.hostname", name)
        
        name = cls.re_name.sub("-", name).strip("-")
        
        return cls(id=id_, name=name, ipv4s=ipv4s, ipv6s=ipv6s)

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
        name = _as_str(name)
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
            known_hosts[unique_name] = (info.ipv4s, info.ipv6s)
        
        self.dns_updater.set_hosts(known_hosts)
    
    def on_disconnect(self, container_id):
        if container_id not in self._hosts_cache:
            self.logger.debug("Disconnected container %r was not tracked, ignoring", container_id)
            return
        name = self._hosts_cache[container_id]
        self.logger.info("Removing entry %r as container %r disconnected", name, container_id)
        del self._hosts_cache[container_id]
            
        self.dns_updater.remove_host(name)
    
    def on_connect(self, container_id, name, ipv4s, ipv6s):
        unique_name = self._deduplicate_container_name(name)
        self.logger.info("Adding new entry %r:{ipv4:%r, ipv6:%r} for container %r", unique_name, ipv4s, ipv6s, container_id)
        self._hosts_cache[container_id] = unique_name
        self.dns_updater.add_host(unique_name, ipv4s, ipv6s)
        
    def handle_event(self, event):
        if event["Type"] == "network":
            if event["Action"] == "connect":
                container_id = event["Actor"]["Attributes"]["container"]
                self.logger.debug("Handling connect event for container %r", container_id)
                info = ContainerInfo.from_container(self.client.containers.get(container_id))
                self.on_connect(container_id, info.name, info.ipv4s, info.ipv6s)
            
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
