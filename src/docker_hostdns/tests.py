'''
Created on 07.04.2017

@author: glorpen
'''
import unittest.mock
from docker_hostdns.hostdns import NamedUpdater
import dns
import contextlib

class NamedUpdaterTest(unittest.TestCase):
    
    hostname = "example-host"
    host4_a = "192.168.1.1"
    host4_b = "192.168.1.2"
    host6 = "fe80::7e5c:f8ff:fe84:a792"
    
    @contextlib.contextmanager
    def mock_dns_query(self, protocol = 'tcp'):
        with unittest.mock.patch("dns.query.%s" % protocol) as f:
            ret = unittest.mock.MagicMock()
            ret.rcode.return_value = dns.rcode.NOERROR
            f.return_value = ret
            
            yield f, ret
    
    def assert_dns_rrset(self, update, name, rtype, value, deleting=None):
        found = False
        
        for i in update.authority:
            if i.match(dns.name.from_text(name), dns.rdataclass.IN, rtype, covers=dns.rdatatype.NONE, deleting=deleting):
                found = (not i.items and value is None) or (i.items[0].to_text().strip('"') == value)
                if found:
                    break
                
        self.assertTrue(found, "%r %s dns record with value %r exists" % (name, dns.rdatatype.to_text(rtype), value))
    
    def create_obj(self):
        return NamedUpdater("example-zone", "example-dns")
    
    def test_host_add(self):
        n = self.create_obj()
        
        self.assertFalse(n.hosts)
        with self.mock_dns_query() as (f, _ret):
            n.add_host(self.hostname, [self.host4_a, self.host4_b], [self.host6])
            
            self.assertTrue(n.hosts.issubset([self.hostname]))
            
            f.assert_called_once()
            update = f.call_args[0][0]
            
            # check if update-set contains add commands
            self.assert_dns_rrset(update, "_container", dns.rdatatype.TXT, self.hostname)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.A, self.host4_a)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.A, self.host4_b)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.AAAA, self.host6)
            
    def test_host_remove(self):
        n = self.create_obj()
        n.hosts.add(self.hostname)
        with self.mock_dns_query() as (f, _ret):
            n.remove_host(self.hostname)
            self.assertFalse(n.hosts)
            
            f.assert_called_once()
            update = f.call_args[0][0]
            
            # check if update-set contains removal commands
            self.assert_dns_rrset(update, "_container", dns.rdatatype.TXT, self.hostname, deleting=dns.rdataclass.NONE)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.A, None, deleting=dns.rdataclass.ANY)
            self.assert_dns_rrset(update, "*.%s" % self.hostname, dns.rdatatype.A, None, deleting=dns.rdataclass.ANY)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.AAAA, None, deleting=dns.rdataclass.ANY)
            self.assert_dns_rrset(update, "*.%s" % self.hostname, dns.rdatatype.AAAA, None, deleting=dns.rdataclass.ANY)
    
    def test_host_set(self):
        n = self.create_obj()
        n.hosts.add(self.hostname)
        with self.mock_dns_query():
            n.add_host("second-host", ["127.0.0.1"])
        
        self.assertTrue(n.hosts.issubset([self.hostname, "second-host"]))
    
    def test_load_hosts(self):
        n = self.create_obj()
        with self.mock_dns_query('udp') as (_f, ret):
            ret.answer = "test"
            ret.find_rrset.return_value = [
                dns.rdtypes.ANY.TXT.TXT(dns.rdataclass.IN, dns.rdatatype.TXT, [self.hostname])
            ]
            
            n.load_records()
        
        self.assertTrue(n.hosts.issubset([self.hostname]))
