#! /usr/bin/env python

# yuppi_controller.py -- P. Demorest, 2015/02
#
# Based on code originally in async_mcast.py by PD and S. Ransom
#
# This is the actual top-level script that listens for VCI and OBS 
# XML data, and launches pulsar observations as appropriate.

import os
import logging
import asyncore
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from mcast_clients import VCIClient, ObsClient
from evla_config import EVLAConfig, SubBand

from optparse import OptionParser
cmdline = OptionParser()
cmdline.add_option('-v', '--verbose', dest="verbose",
        action="store_true", default=False,
        help="More verbose output")
cmdline.add_option('-l', '--listen', dest="listen",
        action="store_true", default=False,
        help="Only listen to multicast, don't launch anything") 
cmdline.add_option('-U', '--config_url', dest="config_url",
        action="store_true", default=False,
        help="Use config URL to retrieve VCI")
(opt,args) = cmdline.parse_args()

# Set up verbosity level for log
loglevel = logging.INFO
if opt.verbose:
    loglevel = logging.DEBUG

logging.basicConfig(format="%(asctime)-15s %(levelname)8s %(message)s",
        level=loglevel)

os.nice(10)

logging.info('yuppi_controller started')

if opt.config_url:
    logging.info('will retrieve VCI from configUrl')
else:
    logging.info('will listen for VCI multicast')

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
        # Also clear stopped observations
        self.observations = [o for o in self.observations if not o.is_stopped()]

    def handle_config(self,config):
        if not config.is_complete():
            logging.error('handle_config called on incomplete configuration')
            return

        logging.info("complete config Id='%s' seq=%d intent='%s' wait=%+.1fs" % (
            config.obs.configId, config.seq, config.scan_intent,
            config.wait_time_sec))

        try:

            if 'PULSAR_' in config.scan_intent:

                subbands = config.get_subbands(match_ips=data_ips)
                logging.info("found %d matching subbands" % len(subbands))

                # if there is a running observation we need to stop it..
                for observation in self.observations:

                    # Skip any not associated with the same datasetId.
                    # This allows multiple subarrays to run without
                    # stomping on each other.
                    if observation.datasetId != config.datasetId: continue

                    logging.debug('request stop obs %s in %.1fs' % (
                        observation.id, config.wait_time_sec))
                    # Two pulsar scans back-to-back, allow an extra half-second
                    # delay between them by ending first one early:
                    observation.stop_at(config.startTime - 0.5/86400.0) 

                # Allow multiple subbands
                # TODO check for max simultaneous subbands here?
                daq_idx=0
                for sub in subbands:
                    logging.info("configuring subband %s-%d %.1fMHz" % (
                        sub.IFid, sub.swIndex-1, sub.sky_center_freq))

                    # Launch observation at the right time
                    self.observations += [YUPPIObs(config,sub,daq_idx=daq_idx),]
                    daq_idx += 1

            else:

                # Non-pulsar config, send stop to all running obs at the
                # appropriate time
                for observation in self.observations:
                    # Skip any from other subarrays:
                    if observation.datasetId != config.datasetId: continue
                    logging.debug('request stop obs %s in %.1fs' % (observation.id,
                        config.wait_time_sec))
                    observation.stop_at(config.startTime)

        except:
            logging.exception("exception in handle_config():")

if __name__ == '__main__':
    # This starts the receiving/handling loop
    controller = YUPPIController()
    if not opt.config_url:
        vci_client = VCIClient(controller)
    obs_client = ObsClient(controller,use_configUrl=opt.config_url)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        # Just exit without the trace barf
        logging.info('yuppi_controller got SIGINT, exiting')
