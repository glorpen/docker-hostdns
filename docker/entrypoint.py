#!/usr/local/bin/python

"""
@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
"""

import os
import sys
import docker_hostdns.console as dconsole

app_args = sys.argv[1:]

if len(sys.argv) > 1 and app_args[0][0] != "-":
	os.execvp(app_args[0], app_args)

pre_args = []

key_secret = os.environ.get("DNS_KEY_SECRET")
if key_secret is None:
	secret_file = os.environ.get("DNS_KEY_SECRET_FILE")
	if secret_file:
		with open(secret_file, "rt") as f:
			key_secret = f.read()

if key_secret:
	pre_args.extend(["--dns-key-secret", key_secret])

dns_key_name = os.environ.get("DNS_KEY_NAME")
if dns_key_name:
	pre_args.extend(["--dns-key-name", dns_key_name])

dns_zone = os.environ.get("DNS_ZONE")
if dns_zone:
        pre_args.extend(["--zone", dns_zone])

dns_server = os.environ.get("DNS_SERVER")
if dns_server:
        pre_args.extend(["--dns-server", dns_server])

instance_name = os.environ.get("NAME")
if instance_name:
	pre_args.extend(["--name", instance_name])

network = os.environ.get("NETWORK")
if network:
        net_list = [x.strip() for x in network.split(',')]
        for network in net_list:
                pre_args.extend(["--network", network])

verbosity = os.environ.get("VERBOSITY")
if verbosity:
        try:
                verb_int = int(verbosity)
        except ValueError:
                verb_int = None

        if verb_int:
                verbosity = '-'
                count = 0
                for count in range(min(verb_int, 3)):
                        verbosity += 'v'
                        count += 1
                pre_args.extend([verbosity])

syslog = os.environ.get("SYSLOG")
if syslog and syslog.lower() in ["true", "yes"]:
	pre_args.extend(["--syslog"])

clear_on_exit = os.environ.get("CLEAR_ON_EXIT")
if clear_on_exit and clear_on_exit.lower() in ["true", "yes"]:
	pre_args.extend(["--clear-on-exit"])

dconsole.execute([sys.argv[0]] + pre_args + app_args)
