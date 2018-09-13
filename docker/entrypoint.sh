#!/bin/sh

#
# author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
#

set -e

has_key_file(){
	test -f "${DNS_KEY_SECRET_FILE}"
	return $?
}
has_key_env(){
	test "${DNS_KEY_SECRET+x}" == "x"
	return $?
}

if [ "${1:0:1}" = '-' ] || [ "${@}" == '' ];
then
	_args=''
	if has_key_file || has_key_env;
	then
		_args="${_args} --dns-key-secret -"
	fi
	
	if has_key_file;
	then
		cat "${DNS_KEY_SECRET_FILE}"
	else
		echo "${DNS_KEY_SECRET}"
	fi \
	| exec python -m docker_hostdns ${_args} "$@"
else
	exec "$@"
fi
