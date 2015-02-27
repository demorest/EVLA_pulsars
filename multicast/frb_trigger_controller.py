#! /usr/bin/env python

# frb_trigger_controller.py -- P. Demorest, 2015/02
#
# Listen for OBS packets having a certain 'triggered archiving'
# intent, and perform some as-yet-unspecified action when these
# are recieved.

import os
import logging
import asyncore
from mcast_clients import ObsClient
from evla_config import EVLAConfig

from optparse import OptionParser
cmdline = OptionParser()
cmdline.add_option('-v', '--verbose', dest="verbose",
        action="store_true", default=False,
        help="More verbose output")
cmdline.add_option('-l', '--listen', dest="listen",
        action="store_true", default=False,
        help="Only listen to multicast, don't launch anything") 
(opt,args) = cmdline.parse_args()

progname = 'frb_trigger_controller'

# Set up verbosity level for log
loglevel = logging.INFO
if opt.verbose:
    loglevel = logging.DEBUG

logging.basicConfig(format="%(asctime)-15s %(levelname)8s %(message)s",
        level=loglevel)

logging.info('%s started' % progname)

if opt.listen:
    logging.info('runnning in listen-only mode')

node = os.uname()[1]

class FRBController(object):
    """Listens for OBS packets and tells FRB processing about any
    notable scans."""

    def __init__(self):
        # Note, replace these with whatever real intent we want to 
        # trigger on
        self.trigger_intent = 'VLITE_OFF'
        self.trigger_value = '0'

    def add_obs(self,obs):
        config = EVLAConfig(vci=None,obs=obs)
        if self.trigger_intent in config.intents:
            if config.intents[self.trigger_intent] == self.trigger_value:
                logging.info("Received trigger intent")
                if not opt.listen:
                    # TODO: do whatever we need to do here
                    pass

if __name__ == '__main__':
    # This starts the receiving/handling loop
    controller = FRBController()
    obs_client = ObsClient(controller)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        # Just exit without the trace barf
        logging.info('%s got SIGINT, exiting' % progname)
