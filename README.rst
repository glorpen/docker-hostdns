==============
Docker HostDNS
==============

Update BIND nameserver zone with Docker hosts via DNS Updates.

Usage
=====

.. sourcecode::

   usage: docker-hostdns [-h] [--zone ZONE] [--dns-server DNS_SERVER]
                         [--dns-key-secret DNS_KEY_SECRET]
                         [--dns-key-name DNS_KEY_NAME] [--daemonize] [--verbose]
                         [--syslog]
   
   optional arguments:
     -h, --help            show this help message and exit
     --zone ZONE           Dns zone to update
     --dns-server DNS_SERVER
                           Address of DNS server which will be updated
     --dns-key-secret DNS_KEY_SECRET
                           DNS Server key secret for use when updating zone. Use
                           '-' to read from stdin.
     --dns-key-name DNS_KEY_NAME
                           DNS Server key name for use when updating zone
     --daemonize, -d       Daemonize after start
     --verbose, -v         Give more output. Option is additive, and can be used
                           up to 3 times.
     --syslog              Log to syslog

