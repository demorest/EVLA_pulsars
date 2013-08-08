#!/usr/bin/env python
#from collections import OrderedDict 
from ordereddict import OrderedDict # For python 2.6
from psrinfo_mcast import *
from guppi_daq import guppi_utils
import time, struct, socket, sys, asyncore, subprocess
import vcirequest_mcast
import observation_mcast
import netifaces

mcast_types = ["obs", "vci"]
ports = {"obs": 53001, "vci": 53000}
groups = {"obs": '239.192.3.2', "vci": '239.192.3.1'}
use_shmem = True
debugout = False

# Figure out which IP addresses we might get data packets on
data_ips = []
for i in netifaces.interfaces():
    if 'p2p' in i:
        data_ips += [netifaces.ifaddresses(i)[netifaces.AF_INET][0]['addr']]
print "Detected IPs:", data_ips

configs = OrderedDict()
configstosave = 5

def push_to_shmem(conf):
    global g
    g.read()
    g.update("SRC_NAME", conf.source)
    g.update("OBSERVER", conf.observer)
    g.update("RA_STR", conf.ra_str)
    g.update("DEC_STR", conf.dec_str)
    g.update("TELESCOP", conf.telescope)
    g.update("FRONTEND", conf.receiver)
    g.update("PROJID", conf.projid)
    g.update("FD_POLN", "CIRC")
    g.update("TRK_MODE", "TRACK")
    g.update("OBSFREQ", conf.skyctrfreq)
    g.update("OBSBW", conf.bandwidth)
    g.update("OBS_MODE", "VDIF")
    g.update("CAL_MODE", "OFF")
    g.update("BACKEND", conf.backend)
    g.update("LST", conf.startLST)
    if conf.subbands[0].vdif:
        v = conf.subbands[0].vdif
        g.update("PKTSIZE", int(v.frameSize)*4+32) # frameSize is in words
        g.update("VDIFTIDA", int(v.aThread))
        g.update("VDIFTIDB", int(v.bThread))
        g.update("DATAPORT", int(v.aDestPort)) # Assume same port for both
    g.write()
    g.show()
    
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
        configs[obj.configId].parse(match_ips=data_ips)
        cc = configs[obj.configId]
        if debugout:
            print cc.__dict__
            for subband in cc.subbands:
                print subband.__dict__
        if use_shmem:
            push_to_shmem(cc)
        if ('PULSAR_FOLD' in cc.scan_intent) or \
               ('PULSAR_SEARCH' in cc.scan_intent):
            call_dspsr(cc)
            

def call_dspsr(conf):
    if 'PULSAR_FOLD' in conf.scan_intent:
        # construct command line, referring to .par file
        # and building the output file name from what should
        # be unique identifiers [TBC]
        command_args = ('dspsr -header INSTRUMENT=guppi_daq DATABUF=1 -a PSRFITS -minram=1 -t6 -F256:D -L10. -E /lustre/evla/pulsar/data/%s.par -b 1024 -O /lustre/evla/pulsar/data/%s.%s.%s' % (conf.source, conf.source, conf.projid, conf.seq)).split(' ')
    else:  # PULSAR_SEARCH 
        # construct command line, building the output file name
        # from what should be unique identifiers [TBC]
        command_line = 'digifil -F1024:D -o /lustre/evla/pulsar/%s.%s.FITS' % (conf.projid, conf.seq)
    print "Pulsar observation!  Command: ", command_args
    #subprocess.Popen(command_args)
    #time.sleep(1)
    #open('/tmp/guppi_daq_control','w').write('START')

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
            if debugout: print self.type, ":", obj.configId, obj.seq
            add_config(obj, self.type)
        elif (self.type=="vci" and not "AntennaPropertyTable" in self.read):
            obj = vcirequest_mcast.parseString(self.read)
            if debugout: print self.type, ":", obj.configId
            add_config(obj, self.type)
        else:
            print self.type, ": Unknown message"

if __name__ == '__main__':
    if use_shmem:
        g = guppi_utils.guppi_status()
    clients = [mcast_client(groups[x], ports[x], x) for x in mcast_types]
    asyncore.loop()
