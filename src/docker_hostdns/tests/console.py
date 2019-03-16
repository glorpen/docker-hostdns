'''
@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
'''
import unittest
from docker_hostdns import console
import socket

class ConsoleTest(unittest.TestCase):
    test_path = "/some/path"
    test_host = "some-host"
    
    def test_syslog_argument_parsing(self):
        o = console.parse_commandline(["prog", "--syslog"])
        self.assertEqual(o.syslog.path, "/dev/log", "default syslog socket when not specified")
        
        o = console.parse_commandline(["prog", "--syslog", self.test_path])
        self.assertEqual(o.syslog.path, self.test_path, "syslog with unix socket when scheme is not provided")
        self.assertIsNone(o.syslog.socket)
        
        o = console.parse_commandline(["prog", "--syslog", "unix://"+self.test_path])
        self.assertEqual(o.syslog.path, self.test_path)
        self.assertIsNone(o.syslog.socket)
        
        o = console.parse_commandline(["prog", "--syslog", "udp://"+self.test_host])
        self.assertEqual(o.syslog.hostname, self.test_host)
        self.assertEqual(o.syslog.socket, socket.SOCK_DGRAM)
        self.assertEqual(o.syslog.port, 514, "use default syslog port if not provided")
        
        o = console.parse_commandline(["prog", "--syslog", "tcp://%s:1234" % self.test_host])
        self.assertEqual(o.syslog.socket, socket.SOCK_STREAM)
        self.assertEqual(o.syslog.hostname, self.test_host)
        self.assertEqual(o.syslog.port, 1234)
