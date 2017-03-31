'''
Created on 31.03.2017

@author: glorpen
'''

class AppException(Exception):
    pass

class ConnectionException(AppException):
    pass

class ConfigException(AppException):
    pass
