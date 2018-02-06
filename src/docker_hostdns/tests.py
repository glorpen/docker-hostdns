'''
Created on 07.04.2017

@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
'''
import unittest.mock
from docker_hostdns.hostdns import NamedUpdater, ContainerInfo, DockerHandler
import dns
import contextlib
from docker_hostdns.exceptions import ConnectionException
import socket

def _assert_called_once(mock):
    if hasattr(mock, "assert_called_once"):
        return mock.assert_called_once
    else:
        def _assert(*args, **kwargs):
            assert mock.called
    

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
        
        zone = update.question[0].name
        
        for i in update.authority:
            if i.match(dns.name.from_text(name, zone), dns.rdataclass.IN, rtype, covers=dns.rdatatype.NONE, deleting=deleting):
                found = (not i.items and value is None) or (i.items[0].to_text().strip('"') == value)
                if found:
                    break
                
        self.assertTrue(found, "%r %s dns record with value %r exists" % (name, dns.rdatatype.to_text(rtype), value))
    
    def create_obj(self):
        return NamedUpdater("example-zone", "example-dns", instance_name="test")
    
    def test_host_add(self):
        n = self.create_obj()
        
        self.assertFalse(n.hosts)
        with self.mock_dns_query() as (f, _ret):
            n.add_host(self.hostname, [self.host4_a, self.host4_b], [self.host6])
            
            self.assertTrue(n.hosts.issubset([self.hostname]))
            
            _assert_called_once(f)
            update = f.call_args[0][0]
            
            # check if update-set contains add commands
            self.assert_dns_rrset(update, "_container_test", dns.rdatatype.TXT, self.hostname)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.A, self.host4_a)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.A, self.host4_b)
            self.assert_dns_rrset(update, self.hostname, dns.rdatatype.AAAA, self.host6)
            
    def test_host_remove(self):
        n = self.create_obj()
        n.hosts.add(self.hostname)
        with self.mock_dns_query() as (f, _ret):
            n.remove_host(self.hostname)
            self.assertFalse(n.hosts)
            
            _assert_called_once(f)
            update = f.call_args[0][0]
            
            # check if update-set contains removal commands
            self.assert_dns_rrset(update, "_container_test", dns.rdatatype.TXT, self.hostname, deleting=dns.rdataclass.NONE)
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

class ContainerInfoTest(unittest.TestCase):
    
    test_id = "some-id"
    
    def create_container(self, id_, name, networks={}, label_name=None):
        m = unittest.mock.Mock()
        
        m.attrs = {
            "Id": id_,
            "Name": name,
            "NetworkSettings": {
                "Networks": {}
            },
            "Config": {
                "Labels": {}
            }
        }
        
        for name, v in networks.items():
            m.attrs["NetworkSettings"]["Networks"][name] = {
                "IPAddress": v[0],
                "GlobalIPv6Address": v[1]
            }
        if label_name:
            m.attrs["Config"]["Labels"]["pl.glorpen.hostname"] = label_name
        
        return m
    
    def test_getter_without_networks(self):
        m = self.create_container(self.test_id, "/some_test__")
        c = ContainerInfo.from_container(m)
        self.assertEqual(c.id, self.test_id)
        self.assertEqual(c.name, "some-test")
        self.assertEqual(c.ipv4s, [])
        self.assertEqual(c.ipv6s, [])
    
    def test_label(self):
        m = self.create_container(self.test_id, self.test_id, label_name="name_from_label")
        c = ContainerInfo.from_container(m)
        self.assertEqual(c.name, "name-from-label")
    
    def test_networks(self):
        m = self.create_container(
            self.test_id,
            self.test_id,
            networks={"a":["ipv4.1","ipv6.1"],"b":["ipv4.2", None], "c":[None, "ipv6.2"]}
        )
        c = ContainerInfo.from_container(m)
        self.assertEqual(sorted(c.ipv4s), ["ipv4.1", "ipv4.2"])
        self.assertEqual(sorted(c.ipv6s), ["ipv6.1", "ipv6.2"])

class DockerHandlerTest(unittest.TestCase):
    def get_object(self):
        dns_updater = unittest.mock.MagicMock()
        d = DockerHandler(dns_updater)
        
        return d, dns_updater
    
    @contextlib.contextmanager
    def mock_docker_client(self):
        with unittest.mock.patch("docker.from_env") as docker:
            client = unittest.mock.MagicMock()
            docker.return_value = client
            
            yield client
    
    @contextlib.contextmanager
    def mock_container_info_factory(self):
        with unittest.mock.patch.object(ContainerInfo, 'from_container') as cinfo:
            yield cinfo
    
    def test_setup_error(self):
        d, _updater = self.get_object()
        with self.mock_docker_client() as client:
            client.ping.side_effect = Exception()
            self.assertRaises(ConnectionException, d.setup)
    
    def test_setup(self):
        d, updater = self.get_object()
        with self.mock_docker_client() as client:
            client.containers.list.return_value = [
                ["idA", "a", ["ipv4"], ["ipv6"]],
                ["idB", "b", ["ipv4"], []],
                ["idC", "a", [], []],
            ]
            with self.mock_container_info_factory() as info:
                info.side_effect = lambda c: ContainerInfo(id=c[0],name=c[1], ipv4s=c[2], ipv6s=c[3])
                d.setup()
        
        # second "a" should be renamed to a-1
        updater.set_hosts.assert_called_once_with({'b': (['ipv4'], []), 'a-1': ([], []), 'a': (['ipv4'], ['ipv6'])})
    
    def test_connection_events_handlers(self):
        d, updater = self.get_object()
        
        d.on_disconnect("unknown-id")
        updater.remove_host.assert_not_called()
        
        d.on_connect("known-id", "name", ["ipv4"],["ipv6"])
        updater.add_host.assert_called_once_with("name", ["ipv4"], ["ipv6"])
        d.on_disconnect("known-id")
        updater.remove_host.assert_called_once_with("name")
    
    def test_connection_events_dispatcher(self):
        with unittest.mock.patch.object(DockerHandler, 'on_connect') as on_connect:
            with unittest.mock.patch.object(DockerHandler, 'on_disconnect') as on_disconnect:
                d, updater = self.get_object()
                
                with self.mock_container_info_factory() as info:
                    with self.mock_docker_client() as client:
                        
                        d.setup()
                        
                        c = ContainerInfo(id="container-1", name="c-1")
                        info.return_value = c
                        
                        d.handle_event({
                            "Type": "network",
                            "Action": "connect",
                            "Actor":{"Attributes":{"container":"test-id"}}
                        })
                        
                        on_connect.assert_called_once_with("test-id", "c-1", None, None)
                        
                        d.handle_event({
                            "Type": "network",
                            "Action": "disconnect",
                            "Actor":{"Attributes":{"container":"test-id"}}
                        })
                        
                        on_disconnect.assert_called_once_with("test-id")
        