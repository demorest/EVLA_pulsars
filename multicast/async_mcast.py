#!/usr/bin/env python2.7
from collections import OrderedDict 
from psrinfo_mcast import *
import time, struct, socket, sys, asyncore
import vcirequest_mcast
import observation_mcast

mcast_types = ["obs", "vci"]
ports = {"obs": 53001, "vci": 53000}
groups = {"obs": '239.192.3.2', "vci": '239.192.3.1'}

configs = OrderedDict()
configstosave = 5

def add_config(obj, type):
    global configs
    if not configs.has_key(obj.configId):
        configs[obj.configId] = EVLA_config()
    if type in mcast_types:
        setattr(configs[obj.configId], type, obj)
    else:
        print "unknown mcast type in add_config()"
    # limit the length of configs
    if len(configs) > configstosave:
        configs.popitem(last=False)
    # print if we have a complete config
    if (hasattr(configs[obj.configId], "vci") and
        hasattr(configs[obj.configId], "obs")):
        print "Have complete config for", obj.configId
        configs[obj.configId].parse()
        print configs[obj.configId].__dict__
        for subband in configs[obj.configId].subbands:
            print subband.__dict__

class mcast_client(asyncore.dispatcher):

    def __init__(self, group, port, type):
        asyncore.dispatcher.__init__(self)
        self.type = type
        self.group = group
        self.port = port
        self.addrinfo = socket.getaddrinfo(group, None)[0]
        self.create_socket(self.addrinfo[0], socket.SOCK_DGRAM)
        self.set_reuse_addr()
        self.bind(('', port))
        group_bin = socket.inet_pton(self.addrinfo[0], self.addrinfo[4][0])
        mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
        self.socket.setsockopt(socket.IPPROTO_IP,
                               socket.IP_ADD_MEMBERSHIP, mreq)
        self.read = None

    def handle_connect(self):
        print self.type, self.group, self.port, "connect"

    def handle_close(self):
        print self.type, "close"
        self.close()

    def writable(self):
        return False
        
    def handle_read(self):
        self.lastread = self.read
        self.read = self.recv(100000)
        if (self.type=="obs"):
            obj = observation_mcast.parseString(self.read)
            print self.type, ":", obj.configId, obj.seq
            add_config(obj, self.type)
        elif (self.type=="vci" and not "AntennaPropertyTable" in self.read):
            obj = vcirequest_mcast.parseString(self.read)
            print self.type, ":", obj.configId
            add_config(obj, self.type)
        else:
            print self.type, ": Unknown message"

if __name__ == '__main__':
    clients = [mcast_client(groups[x], ports[x], x) for x in mcast_types]
    asyncore.loop()
