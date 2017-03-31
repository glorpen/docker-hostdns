'''
Created on 31.03.2017

@author: Arkadiusz Dzięgiel <arkadiusz.dziegiel@glorpen.pl>
'''

class AppException(Exception):
    pass

class ConnectionException(AppException):
    pass

class ConfigException(AppException):
    pass

class DnsException(AppException):
    pass

class StopException(AppException):
    pass
