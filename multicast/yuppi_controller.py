#! /usr/bin/env python

# yuppi_controller.py -- P. Demorest, 2015/02
#
# Based on code originally in async_mcast.py by PD and S. Ransom
#
# This is the actual top-level script that listens for VCI and OBS 
# XML data, and launches pulsar observations as appropriate.

import os
import struct
import logging
import asyncore, socket
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import vcixml_parser
import obsxml_parser
from evla_config import EVLAConfig, SubBand

from optparse import OptionParser
cmdline = OptionParser()
cmdline.add_option('-v', '--verbose', dest="verbose",
        action="store_true", default=False,
        help="More verbose output")
cmdline.add_option('-l', '--listen', dest="listen",
        action="store_true", default=True,
        help="Only listen to multicast, don't launch anything") 
(opt,args) = cmdline.parse_args()

# Set up verbosity level for log
loglevel = logging.INFO
if opt.verbose:
    loglevel = logging.DEBUG

logging.basicConfig(format="%(asctime)-15s %(levelname)8s %(message)s",
        level=loglevel)

logging.info('yuppi_controller started')

data_ips = []
if opt.listen:
    logging.info('runnning in listen-only mode')
else:
    # Get the list of IP addresses on which VDIF data may come
    import netifaces
    from yuppi_observation import YUPPIObs
    for nic in netifaces.interfaces():
        if 'p2p' in nic:
            data_ips += \
                    [netifaces.ifaddresses(nic)[netifaces.AF_INET][0]['addr']]
    logging.info('found data IPs: ' + str(data_ips))

node = os.uname()[1]

class McastClient(asyncore.dispatcher):
    """Generic class to receive the multicast XML docs."""

    def __init__(self, group, port, name=""):
        asyncore.dispatcher.__init__(self)
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

    def handle_close(self):
        logging.debug('close %s group=%s port=%d' % (self.name, 
            self.group, self.port))

    def writeable(self):
        return False

    def handle_read(self):
        self.read = self.recv(100000)
        logging.debug('read ' + self.name + ' ' + self.read)
        try:
            self.parse()
        except Exception as e:
            logging.error('error handling message: ' + repr(e))

    def handle_error(self, type, val, trace):
        logging.error('unhandled exception: ' + repr(val))

class ObsClient(McastClient):
    """Receives Observation XML."""

    def __init__(self,controller):
        McastClient.__init__(self,'239.192.3.2',53001,'obs')
        self.controller = controller

    def parse(self):
        obs = obsxml_parser.parseString(self.read)
        logging.info("read obs configId='%s' seq=%d" % (obs.configId,
            obs.seq))
        self.controller.add_obs(obs)

class VCIClient(McastClient):
    """Receives VCI XML."""

    def __init__(self,controller):
        McastClient.__init__(self,'239.192.3.1',53000,'vci')
        self.controller = controller

    def parse(self):
        vci = vcixml_parser.parseString(self.read)
        if type(vci) == vcixml_parser.subArray:
            logging.info("read vci configId='%s'" % vci.configId)
            self.controller.add_vci(vci)
        else:
            logging.info("read vci non-subArray, ignoring" % vci.configId)

class YUPPIController(object):
    """Stores received VCI and Obs structures and pairs them up by
    matching configId.  Generates EVLAConfig and (when necessary) 
    YUPPIObs objects from each matching pair."""

    def __init__(self, max_vci_store=5):
        self.max_vci_store = max_vci_store
        self.vci = OrderedDict()
        self.orphan_configs = [] # Configs with no matching VCI
        self.observations = []   # Ongoing/upcoming observations

    def add_vci(self,vci):
        # Add it to the list
        self.vci[vci.configId] = vci
        # Check if this matches any of the orphan configs
        for config in self.orphan_configs:
            if config.Id == vci.configId:
                config.set_vci(vci)
                self.handle_config(config)
        # Strip complete entries from the orphan list
        self.orphan_configs = [c for c in self.orphan_configs 
                if not c.is_complete()]
        # Remove old VCIs
        while len(self.vci) > self.max_vci_store:
            self.vci.popitem(last=False)
        # Remove timed-out obs
        self.clear_orphans()

    def add_obs(self,obs):
        config = EVLAConfig(obs=obs)
        if obs.configId in self.vci:
            config.set_vci(self.vci[obs.configId])
            self.handle_config(config)
        else:
            logging.info("got orphan obs configId='%s' seq=%d wait=%+.1fs" % (
                config.Id, config.seq, config.wait_time_sec))
            self.orphan_configs += [config,]
        # Remove timed-out obs
        self.clear_orphans()

    def clear_orphans(self):
        # Clear any orphan configs with start time greater than 10s(?)
        # in the past.
        for idx, config in enumerate(self.orphan_configs):
            if config.wait_time_sec < -10.0:
                logging.info("dropping orphan configId='%s' seq=%d" % (
                    config.Id, config.seq))
                self.orphan_configs[idx] = None
        self.orphan_configs = [c for c in self.orphan_configs if c is not None]

    def handle_config(self,config):
        if not config.is_complete():
            logging.error('handle_config called on incomplete configuration')
            return

        logging.info("complete config Id='%s' seq=%d intent='%s' wait=%+.1fs" % (
            config.obs.configId, config.seq, config.scan_intent,
            config.wait_time_sec))

        # TODO actually do something


# This starts the receiving/handling loop
controller = YUPPIController()
vci_client = VCIClient(controller)
obs_client = ObsClient(controller)
try:
    asyncore.loop()
except KeyboardInterrupt:
    # Just exit without the trace barf
    logging.info('yuppi_controller got SIGINT, exiting')
    pass
