1.1.1
=====

- it is now possible to run multiple instances in single dns zone
  `#2 <https://github.com/glorpen/docker-hostdns/pull/2>`__ (`dvenza <https://github.com/dvenza>`__)
- added option to override default instance name for use in txt records

1.1.0
=====

- possible breaking change: changed `dnspython3` package to just `dnspython` as Py3 is now supported

1.0.4
=====

- host names are now allowed to have dots in them

1.0.3
=====

- added tests
- added proper domain names coversion
- added a way to keep track of hosts when adding & removing containers

1.0.2
=====

- fixed error when handling disconnection event without earlier connect one
- added app exception logging
