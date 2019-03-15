#!/usr/local/bin/python

"""
@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
"""

import os
import sys
import argparse
import docker_hostdns.console as dconsole

app_args = sys.argv[1:]

if len(sys.argv) > 1 and app_args[0][0] != "-":
	os.execvp(app_args[0], app_args)

env_conf = {}

envs = [
	(
		{
			"DNS_ZONE": "zone",
			"DNS_KEY_NAME": "dns_key_name",
			"NAME": "name",
			"DNS_SERVER": "dns_server"
		},
		str
	),
	(
		{
			"SYSLOG": "syslog",
			"CLEAR_ON_EXIT": "clear_on_exit"
		},
		lambda x: x.lower() in ["true", "yes", "1", "y"]
	),
	(
		{
			"NETWORK": "network"
		},
		lambda x: [y.strip() for y in x.split(',')]
	),
	(
		{
			"VERBOSITY": "verbose"
		},
		int
	)
]

for env_list, value_normalizer in envs:
	for env_name, conf_key in env_list.items():
		value = os.environ.get(env_name)
		if value:
			try:
				env_conf[conf_key] = value_normalizer(value)
			except Exception as e:
				raise Exception("Error on parsing %s: %r" % (env_name, value)) from e

key_secret = os.environ.get("DNS_KEY_SECRET")
if key_secret is None:
	secret_file = os.environ.get("DNS_KEY_SECRET_FILE")
	if secret_file:
		with open(secret_file, "rt") as f:
			key_secret = f.read()

if key_secret:
	env_conf["dns_key_secret"] = key_secret

conf = vars(dconsole.parse_commandline([sys.argv[0]] + app_args))
conf.update(env_conf)
dconsole.execute_with_configuration(argparse.Namespace(**conf))
