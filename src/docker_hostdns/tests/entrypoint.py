"""
@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
"""

import unittest
import contextlib
import runpy
import os

class EntrypointTest(unittest.TestCase):
    
    _entrypoint_path = os.path.dirname(__file__) + "/../../../docker/entrypoint.py"
    
    @contextlib.contextmanager
    def run_entrypoint(self, env={}, args=[]):
        p_console_exec = unittest.mock.patch("docker_hostdns.console.execute_with_configuration")
        p_argv = unittest.mock.patch("sys.argv", [None] + args)
        p_env = unittest.mock.patch("os.environ", env)
        
        console_exec = p_console_exec.start()
        p_argv.start()
        p_env.start()
        
        try:
            runpy.run_path(self._entrypoint_path)
            
            console_exec.assert_called_once()
            ns = console_exec.call_args[0][0]
            yield ns
        finally:
            p_console_exec.stop()
            p_argv.stop()
            p_env.stop()

    def test_syslog(self):
        with self.run_entrypoint() as ns:
            self.assertIsNone(ns.syslog, "No syslog used if no env nor args")
        with self.run_entrypoint(env={"SYSLOG":"true"}) as ns:
            self.assertEqual(ns.syslog.path, "/dev/log", "Default syslog when env is true")
        with self.run_entrypoint(env={"SYSLOG":"y"}) as ns:
            self.assertEqual(ns.syslog.path, "/dev/log", "Default syslog when env is y")
        
        with self.run_entrypoint(env={"SYSLOG":"/dev/test"}) as ns:
            self.assertEqual(ns.syslog.path, "/dev/test", "Unix socket path")
        with self.run_entrypoint(env={"SYSLOG":"tcp://test:1234"}) as ns:
            self.assertEqual(ns.syslog.hostname, "test", "Syslog network target")
    
    def test_network(self):
        with self.run_entrypoint(env={"NETWORK":"test1,test2"}) as ns:
            self.assertEqual(ns.network, ["test1","test2"])
