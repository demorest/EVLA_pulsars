#!/usr/bin/env python
from datetime import datetime
import time, struct, socket, sys, asyncore
import vcirequest_mcast
import observation_mcast

mcast_types = ["obs", "vci"]
ports = {"obs": 53001, "vci": 53000}
groups = {"obs": '239.192.3.2', "vci": '239.192.3.1'}

vci = None
vcilast = None
obs = None
obslast = None

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
        global vci, vcilast, obs, obslast
        self.lastread = self.read
        self.read = self.recv(100000)
        if (self.type=="obs"):
            obslast = obs
            obs = observation_mcast.parseString(self.read)
            print self.type, ":", obs.configId, obs.seq
        elif (self.type=="vci" and not "AntennaPropertyTable" in self.read):
            vcilast = vci
            vci = vcirequest_mcast.parseString(self.read)
            print self.type, ":", vci.configId
        else:
            print self.type, ": Unknown message"
        

if __name__ == '__main__':
    clients = [mcast_client(groups[x], ports[x], x) for x in mcast_types]
    asyncore.loop()
