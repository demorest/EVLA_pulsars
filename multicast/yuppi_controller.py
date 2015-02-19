#! /usr/bin/env python

# yuppi_controller.py -- P. Demorest, 2015/02
#
# Based on code originally in async_mcast.py by PD and S. Ransom
#
# This is the actual top-level script that listens for VCI and OBS 
# XML data, and launches pulsar observations as appropriate.

import os
import logging
import netifaces
import asyncore, socket
from ordereddict import OrderedDict
import vcixml_parser
import obsxml_parser
from evla_config import EVLAConfig, SubBand
from yuppi_observation import YUPPIObs

logging.basicConfig(format="%(asctime)-15s %(levelname)8s %(message)s",
        level=logging.INFO)

# Get the list of IP addresses on which VDIF data may come
data_ips = []
for nic in netifaces.interfaces():
    if 'p2p' in nic:
        data_ips += [netifaces.ifaddresses(nic)[netifaces.AF_INET][0]['addr']]
logging.info('found data IPs: ' + str(data_ips))

node = os.uname()[1]

class McastClient(asyncore.dispatcher):
    """Generic class to receive the multicast XML docs."""

    def __init__(self, group, port, name=""):
        super(McastClient,self).__init__()
        self.name = name
        self.group = group
        self.port = port
        addrinfo = socket.getaddrinfo(group, None)[0]
        self.create_socket(addrinfo[0], socket.SOCK_DGRAM)
        self.set_reuse_addr()
        self.bind(('',port))
        mreq = socket.inet_pton(addrinfo[0],addrinfo[4][0]) \
                + struct.pack('=I', socket.INADDR_ANY)
        self.socket.setsockopt(socket.IPPROTO_IP, 
                socket.IP_ADD_MEMBERSHIP, mreq)
        self.read = None

    def handle_connect(self):
        logging.debug('connect %s group=%s port=%d' % (self.name, 
            self.group, self.port))

    def handle_close(self)
        logging.debug('close %s group=%s port=%d' % (self,name, 
            self.group, self.port))

    def writeable(self):
        return False

    def handle_read(self):
        self.read = self.recv(100000)
        logging.debug('read ' + self.name + ' ' + self.read)
        self.parse()

class ObsClient(McastClient):
    """Receives Observation XML."""

    def __init__(self):
        super(ObsClient,self).__init__('239.192.3.2',53001,'obs')

    def parse(self):
        obs = obsxml_parser.parseString(self.read)
        logging.info("read obs configId='%s' seq=%d" % (obs.configId,
            obs.seq))
        # TODO connect to configs...

class VCIClient(McastClient):
    """Receives VCI XML."""

    def __init__(self):
        super(VCIClient,self).__init__('239.192.3.1',53000,'vci')

    def parse(self):
        vci = vcixml_parser.parseString(self.read)
        logging.info("read vci configId='%s'" % vci.configId)
        # TODO connect to configs...

# Store the past few configs...?
# or make a new class for this..
configs = OrderedDict()
max_configs = 5

# This starts the receiving/handling loop
vci_client = VCIClient()
obs_client = ObsClient()
asyncore.loop()