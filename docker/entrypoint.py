#!/usr/local/bin/python

"""
@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
"""

import os
import sys
import docker_hostdns.console as dconsole

app_args = sys.argv[1:]

if app_args[0][0] != "-":
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

dconsole.execute([sys.argv[0]] + pre_args + app_args)
