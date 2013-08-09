#!/usr/bin/env python
#from collections import OrderedDict 
from ordereddict import OrderedDict # For python 2.6
from psrinfo_mcast import *
from guppi_daq import guppi_utils
from guppi_daq.astro_utils import current_MJD
import time, struct, socket, sys, asyncore, subprocess, os
import vcirequest_mcast
import observation_mcast
import netifaces
import threading

mcast_types = ["obs", "vci"]
ports = {"obs": 53001, "vci": 53000}
groups = {"obs": '239.192.3.2', "vci": '239.192.3.1'}
use_shmem = True
debugout = False

print "async_mcast started at ", time.ctime()

# Figure out which IP addresses we might get data packets on
data_ips = []
for i in netifaces.interfaces():
    if 'p2p' in i:
        data_ips += [netifaces.ifaddresses(i)[netifaces.AF_INET][0]['addr']]
print "Detected IPs:", data_ips
sys.stdout.flush()

node = os.uname()[1]

configs = OrderedDict()
configstosave = 5

# This creates a threading.Timer instance that will run at the specified
# time.
def run_at(mjd, func, args=[], kwargs={}):
    diff = (mjd - current_MJD())*86400.0
    if diff<0.0: diff=0.0
    print "Will execute '%s' at mjd=%f in %.1fs" % (func.__name__,
            mjd, diff)
    sys.stdout.flush()
    threading.Timer(diff, func, args, kwargs).start()
    return

def guppi_daq_command(cmd):
    guppi_ctrl = "/tmp/guppi_daq_control"
    if os.path.exists(guppi_ctrl):
        open(guppi_ctrl,'w').write(cmd)
    else:
        print "Error: guppi_daq control FIFO does not exist"
        sys.stdout.flush()

def generate_shmem_config(conf):
    result = {}
    result["SRC_NAME"]=conf.source
    result["OBSERVER"]=conf.observer
    result["RA_STR"]=conf.ra_str
    result["DEC_STR"]=conf.dec_str
    result["TELESCOP"]=conf.telescope
    result["FRONTEND"]=conf.receiver
    result["PROJID"]=conf.projid
    result["FD_POLN"]="CIRC"
    result["TRK_MODE"]="TRACK"
    result["OBSFREQ"]=conf.skyctrfreq
    result["OBSBW"]=conf.bandwidth
    result["OBS_MODE"]="VDIF"
    result["CAL_MODE"]="OFF"
    result["BACKEND"]=conf.backend
    result["LST"]=conf.startLST
    if conf.subbands[0].vdif:
        v = conf.subbands[0].vdif
        result["PKTSIZE"]=int(v.frameSize)*4+32 # frameSize is in words
        result["VDIFTIDA"]=int(v.aThread)
        result["VDIFTIDB"]=int(v.bThread)
        result["DATAPORT"]=int(v.aDestPort) # Assume same port for both
    return result
    
def push_to_shmem(params):
    global g
    g.read()
    for k in params.keys():
        g.update(k, params[k])
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
        sys.stdout.flush()
        configs[obj.configId].parse(match_ips=data_ips)
        cc = configs[obj.configId]
        if debugout:
            print cc.__dict__
            for subband in cc.subbands:
                print subband.__dict__
        if ('PULSAR_FOLD' in cc.scan_intent) or \
               ('PULSAR_SEARCH' in cc.scan_intent):
            print "Pulsar config (%s)" % cc.scan_intent
            if len(cc.subbands)>0:
                # First generate the necessary configs:
                shmem_conf = generate_shmem_config(cc)
                obs_cmd = generate_obs_command(cc)
                print "shmem conf = ", shmem_conf
                print "obs command = '%s'" % obs_cmd
                print "Send START at %f" % cc.startMJD
                sys.stdout.flush()
                # Then apply them.  This is where we should wait until
                # the official start time:
                run_at(cc.startMJD, run_observation, [shmem_conf, obs_cmd])
            else:
                print "No subbands configured"
                sys.stdout.flush()
        else:
            print "Non-pulsar config (%s)" % cc.scan_intent
            print "Send STOP at %f" % cc.startMJD
            sys.stdout.flush()
            # If this is a non-pulsar config we need to stop 
            # any running pulsar processing.
            # This should also not be done until the appropriate time
            run_at(cc.startMJD, stop_observation)

def generate_obs_command(conf):
    output_file = "/lustre/evla/pulsar/data/%s.%s.%s.%s" % (conf.source,
            conf.projid, conf.seq, node)
    if 'PULSAR_FOLD' in conf.scan_intent:
        # Fold command line
        command = 'dspsr -a PSRFITS -minram=1 -t8 -F32:D -L10. -E/lustre/evla/pulsar/data/%s.par -b1024 -O%s' % (conf.source, output_file)
    elif 'PULSAR_SEARCH' in conf.scan_intent:
        # Search command line
        command = 'digifil -B16 -F256 -t128 -b8 -c -o%s.fil' % (output_file)
    else:
        print "Unrecognized pulsar intent='%s'" % conf.scan_intent
        return
    header_args = " -header INSTRUMENT=guppi_daq DATABUF=1"
    command += header_args
    return command

def run_observation(shmem, command):
    stop_observation() # First make sure we're stopped
    push_to_shmem(shmem)
    print "Pulsar observation!  Command: ", command
    sys.stdout.flush()
    subprocess.Popen(command.split(' '))
    time.sleep(1)
    guppi_daq_command('START')

def stop_observation():
    print "Stop observations"
    sys.stdout.flush()
    guppi_daq_command('STOP')
    # These should probably be done in a cleaner way:
    os.system("pkill -TERM dspsr")
    os.system("pkill -TERM digifil")

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
