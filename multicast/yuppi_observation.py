#! /usr/bin/env python

# yuppi_observation.py -- P. Demorest, 2015/02
#
# Based on code originally in async_mcast.py by PD and S. Ransom
#
# These functions convert EVLAConfig objects into shared memory parameters
# and data processing commands for real-time pulsar processing (YUPPI).  A
# YUPPIObs instance represents a certain observing command.
#
# TODO stuff:
#  - figure out how to handle multiple observations running on a node
#    - 1 subarray, multiple subbands
#    - multiple subarrays, multiple subbands
#  - How to deal with stopping observations: This class provides a 'stop'
#    method but the decision is made at a higher level?

import os
import time
import threading
import logging
import signal
import subprocess
from guppi_daq import guppi_utils
from guppi_daq.astro_utils import current_MJD

class YUPPIObs(object):
    """This class represents a YUPPI observation...
    Initialize with a EVLAConfig object and a specific subband...
    dry_run = True means emit log messages about what would have 
    happened, but do not actually touch shmem or run commands.
    """

    def __init__(self, evla_conf, subband, dry_run=False):
        logging.basicConfig(format="%(asctime)-15s %(levelname)8s %(message)s")
        generate_shmem_config(self, evla_conf, subband)
        generate_obs_command(self, evla_conf, subband)
        self.dry = dry_run
        if self.dry:
            logging.warning("dry run mode enabled")
        self.process = None

    def generate_shmem_config(self, evla_conf, subband):
        """Given a EVLAConfig and SubBand, generate the relevant shared
        memory config params and store them in the self.shmem_params dict.
        """
        self.shmem_params = {}

        self.shmem_params["SRC_NAME"] = evla_conf.source
        self.shmem_params["OBSERVER"] = evla_conf.observer
        self.shmem_params["RA_STR"] = evla_conf.ra_str
        self.shmem_params["DEC_STR"] = evla_conf.dec_str
        self.shmem_params["TELESCOP"] = evla_conf.telescope
        self.shmem_params["PROJID"] = evla_conf.projid
        self.shmem_params["LST"] = evla_conf.startLST

        if 'PULSAR_MONITOR' in evla_conf.scan_intent:
            self.shmem_params["OBS_MODE"] = "MONITOR"
        else:
            self.shmem_params["OBS_MODE"] = "VDIF"

        self.shmem_params["FD_POLN"] = "CIRC" # TODO what about low-freqs
        self.shmem_params["TRK_MODE"] = "TRACK"
        self.shmem_params["CAL_MODE"] = "OFF" # TODO what about cal obs
        self.shmem_params["BACKEND"] = "YUPPI" 

        if subband:

            self.shmem_params["FRONTEND"] = subband.receiver
            self.shmem_params["OBSBW"] = subband.bw
            self.shmem_params["TBIN"] = 0.5/abs(subband.bw*1e6)
            self.shmem_params["OBSFREQ"] = subband.sky_center_freq

            if subband.vdif:
                v = subband.vdif
                self.shmem_params["PKTSIZE"]=int(v.frameSize)*4+32 # words->bytes
                self.shmem_params["NBITS"]=int(v.numBits)
                self.shmem_params["VDIFTIDA"]=int(v.aThread)
                self.shmem_params["VDIFTIDB"]=int(v.bThread)
                self.shmem_params["DATAPORT"]=int(v.aDestPort)

    def generate_obs_command(self, evla_conf, subband):
        """Given a EVLAConfig and SubBand, generate the relevant data
        processing command line and store it in self.command_line.
        """

        self.command_line = ""

        # TODO need to clean up output directory, file naming stuff
        node = os.uname()[1]
        self.data_dir = "/lustre/evla/pulsar/data"
        self.outfile_base = "%s.%s.%s.%s" % (evla_conf.source,
                evla_conf.projid, evla_conf.seq, node)
        output_file = '%s/%s' % (self.data_dir, self.outfile_base)

        # Monitor mode, no data processing required here
        if 'PULSAR_MONITOR' in evla_conf.scan_intent:
            self.command_line = ""
            return

        elif 'PULSAR_FOLD' in evla_conf.scan_intent:
            self.command = 'dspsr -a PSRFITS -minram=1 -t8 -2 c0'
            self.command_line += ' -F%d' % evla_conf.nchan
            self.command_line += ' -d%d' % evla_conf.npol
            self.command_line += ' -L%f' % evla_conf.foldtime
            self.command_line += ' -E%f' % evla_conf.parfile
            self.command_line += ' -b%d' % evla_conf.foldbins
            self.command_line += ' -O%d' % output_file

        elif 'PULSAR_SEARCH' in evla_conf.scan_intent:
            acclen = int(abs(conf.timeres*conf.bandwidth*1e6/conf.nchan))
            self.command_line = 'digifil -threads 8 -B64 -I0 -c'
            self.command_line += ' -F%d' % evla_conf.nchan
            self.command_line += ' -t%d' % acclen
            self.command_line += ' -b%d' % evla_conf.nbitsout
            self.command_line += ' -o%s.fil' % output_file

        else:
            logging.warning("unrecognized intent '%s'" % evla_conf.scan_intent)
            self.command_line = ""
            return

        # Tack on guppi_daq args common to both dspsr and digifil
        # TODO For multiple input streams will need to select databuf value
        self.command_line += " -header INSTRUMENT=guppi_daq DATABUF=1"

    def guppi_daq_command(self,cmd):
        self.guppi_ctrl = "/tmp/guppi_daq_control" # TODO allow multiple
        logging.info("guppi_daq command '%s' to '%s'" % (cmd, self.guppi_ctrl))
        if (os.path.exists(guppi_ctrl)):
            if not self.dry:
                open(guppi_ctrl,'w').write(cmd)
        else:
            logging.error("guppi_daq FIFO '%s' does not exist" % (
                self.guppi_ctrl))

    def update_guppi_shmem(self):
        logging.info('updating shmem: ' + str(self.shmem_params))
        if not self.dry:
            # TODO open here, or keep an open guppi_status...
            g = guppi_utils.guppi_status()
            for k in self.shmem_params:
                g.update(k,self.shmem_params[k])
    
    def start(self):
        logging.info('start observation')
        self.update_guppi_shmem()
        logging.info("command='%s'" % self.command_line)
        if self.command_line and not self.dry:
            logfile = '%s/%s.log' % (self.data_dir, self.outfile_base)
            self.process = subprocess.Popen(self.command_line.split(' '),
                    stdout=open(logfile,'w'), stderr=subprocess.STDOUT)
        time.sleep(1)
        self.guppi_daq_command('START')

    def stop(self):
        logging.info('stop observation')
        self.timer.cancel() # in case not started yet
        self.guppi_daq_command('STOP')
        self.process.send_signal(signal.SIGINT)

