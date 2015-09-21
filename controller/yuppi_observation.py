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

import os
import time
import threading
import logging
import signal
# Original 2.x subprocess is not thread-safe, this is the 3.2 backport:
import subprocess32 as subprocess 
from guppi_daq import guppi_utils
from jdcal import mjd_now

class MJDTimer(object):
    """MJDTimer is based on threading.Timer, but takes a start time
    as an MJD rather than an delay in seconds.  If the start time is in
    the past, the thread will be launched immediately.  The Timer.start()
    method is called immediately when the object is created."""

    def __init__(self,mjd,function,args=[],kwargs={}):
        now = mjd_now()
        diff = (mjd - now)*86400.0
        if (diff<0.0): diff=0.0
        self.timer = threading.Timer(diff,function,args,kwargs)
        self.timer.start()

    def cancel(self):
        self.timer.cancel()

class YUPPIObs(object):
    """This class represents a YUPPI observation, ie real-time
    processing of VDIF packets from one subband.  Initialize with 
    appropriate EVLAConfig and SubBand objects.
    daq_idx = Index of guppi_daq process to use.
    dry_run = True means emit log messages about what would have 
    happened, but do not actually touch shmem or run commands.
    """

    def __init__(self, evla_conf, subband, daq_idx=0, dry_run=False):
        self.state = 'init'
        self.state_lock = threading.Lock()
        self.daq_idx = daq_idx
        self.generate_filename(evla_conf, subband)
        self.generate_shmem_config(evla_conf, subband)
        self.generate_obs_command(evla_conf, subband)
        self.dry = dry_run
        if self.dry:
            logging.warning("dry run mode enabled")
        self.process = None
        self.start_timer = None
        self.stop_timer = None
        self.startMJD = evla_conf.startTime
        self.stopMJD = None
        self.id = evla_conf.Id + '.' + str(evla_conf.seq) + '-' + str(daq_idx)
        self.set_timer()

    def generate_filename(self, evla_conf, subband):
        """Given a EVLAConfig and SubBand, generate the relevant data
        output directory and file name base, and store them in
        self.data_dir and self.outfile_base."""

        node = os.uname()[1]
        node_idx = node.split('-')[-1] # Assumes cbe-node-XX naming

        # This is the old pulsar version:
        #self.data_dir = "/lustre/evla/pulsar/data"
        #self.outfile_base = "%s.%s.%s.%s" % (evla_conf.source,
        #        evla_conf.projid, evla_conf.seq, node)

        # New version, 'normal' VLA data sets (SDM+BDF) are stored
        # using datasetId as the main folder name.  Store here using
        # node-specific subdirs because there are lots of files..
        # Could make a subdir for each datasetId..
        self.data_dir = "/lustre/evla/pulsar/data/%s" % node
        #self.outfile_base = "%s.%d.%s.%s" % (evla_conf.datasetId,
        #        int(evla_conf.seq),evla_conf.source,node_idx)
        self.outfile_base = "%s.%d.%s.%s-%02d" % (evla_conf.datasetId,
                int(evla_conf.seq), evla_conf.source,
                subband.IFid, subband.swIndex-1)

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
        elif 'PULSAR_RAW' in evla_conf.scan_intent:
            self.shmem_params["OBS_MODE"] = "RAW"
        else:
            self.shmem_params["OBS_MODE"] = "VDIF"

        self.shmem_params["FD_POLN"]  = "CIRC" # TODO what about low-freqs
        self.shmem_params["TRK_MODE"] = "TRACK"
        self.shmem_params["CAL_MODE"] = "OFF" # TODO what about cal obs
        self.shmem_params["BACKEND"]  = "YUPPI" 

        self.shmem_params["SCANLEN"]  = 28800.0
        self.shmem_params["PKTFMT"]   = "VDIF"
        self.shmem_params["DATAHOST"] = "any"
        self.shmem_params["POL_TYPE"] = "AABBCRCI"
        self.shmem_params["CAL_FREQ"] = evla_conf.calfreq
        self.shmem_params["CAL_DCYC"] = 0.5
        self.shmem_params["CAL_PHS"]  = 0.0
        self.shmem_params["OBSNCHAN"] = 1
        self.shmem_params["NPOL"]     = 4
        self.shmem_params["PFB_OVER"] = 4
        self.shmem_params["NBITSADC"] = 8
        self.shmem_params["NRCVR"]    = 2
        self.shmem_params["ACC_LEN"]  = 1

        self.shmem_params["DATADIR"] = self.data_dir
        self.shmem_params["BASENAME"] = self.outfile_base
        self.shmem_params["RAWFMT"] = evla_conf.raw_format
        
        # TODO could adjust block size so that there are a round
        # number of frames per block in raw mode.
        self.shmem_params["BLOCSIZE"] = 32000000
        self.shmem_params["OVERLAP"]  = 0

        self.shmem_params["STT_IMJD"] = 57000
        self.shmem_params["STT_SMJD"] = 0
        self.shmem_params["STT_OFFS"] = 0.0

        if subband:

            self.shmem_params["FRONTEND"] = subband.receiver
            self.shmem_params["OBSBW"] = subband.bw
            self.shmem_params["CHAN_BW"] = subband.bw
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
        
        output_file = '%s/%s' % (self.data_dir, self.outfile_base)

        verbosity = ' -q'

        # Monitor or raw record mode, no data processing required here
        if ('PULSAR_MONITOR' in evla_conf.scan_intent
                or 'PULSAR_RAW' in evla_conf.scan_intent):
            self.command_line = ""
            return

        elif 'PULSAR_FOLD' in evla_conf.scan_intent:
            self.command_line = 'dspsr -a PSRFITS -minram=1 -t8 -2 c0'
            self.command_line += ' -F%d:D' % evla_conf.nchan
            self.command_line += ' -d%d' % evla_conf.npol
            self.command_line += ' -L%f' % evla_conf.foldtime
            if evla_conf.parfile == 'CAL':
                # Fold at const freq (eg 10 Hz), no dedispersion, .cf extension
                self.command_line += ' -D0.0001 -c%.10e -e cf' % (1.0/float(evla_conf.calfreq))
            else:
                self.command_line += ' -E%s' % evla_conf.parfile
            self.command_line += ' -b%d' % evla_conf.foldbins
            self.command_line += ' -O%s' % output_file

        elif 'PULSAR_SEARCH' in evla_conf.scan_intent:
            acclen = int(abs(evla_conf.timeres*subband.bw*1e6/evla_conf.nchan))
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
        self.command_line += verbosity
        self.command_line += " -header INSTRUMENT=guppi_daq DATABUF=%d" % (
            1+self.daq_idx*10)

    def guppi_daq_command(self,cmd):
        self.guppi_ctrl = "/tmp/guppi_daq_control_%d" % self.daq_idx
        cmd = cmd.strip()
        logging.info("guppi_daq command '%s' to '%s'" % (cmd, self.guppi_ctrl))
        if (os.path.exists(self.guppi_ctrl)):
            if not self.dry:
                # 1 == line buffering
                open(self.guppi_ctrl,'w',1).write(cmd+'\n')
        else:
            logging.error("guppi_daq FIFO '%s' does not exist" % (
                self.guppi_ctrl))

    def update_guppi_shmem(self):
        logging.info(('updating shmem(%d): ' % self.daq_idx) \
            + str(self.shmem_params))
        if not self.dry:
            # TODO open here, or keep an open guppi_status...
            g = guppi_utils.guppi_status(idx=self.daq_idx)
            for k in self.shmem_params:
                g.update(k,self.shmem_params[k])
            g.write()
    
    def start(self):
        with self.state_lock:
            if self.state=='running':
                logging.warning('obs %s started when already running' % self.id)
                return
            if self.state=='stopped':
                # This should not happen, but if state is stopped then
                # a stop command was already sent, so don't start
                logging.warning('obs %s started when already stopped' % self.id)
                return
            logging.info('start observation %s' % self.id)
            self.update_guppi_shmem()
            logging.info("command='%s'" % self.command_line)
            if self.command_line and not self.dry:
                logfile = '%s/%s.log' % (self.data_dir, self.outfile_base)
                self.process = subprocess.Popen(self.command_line.split(' '),
                        stdout=open(logfile,'w'), stderr=subprocess.STDOUT)
            logging.info("obs %s pre-sleep" % self.id)
            time.sleep(1)
            self.guppi_daq_command('START')
            self.state = 'running'

    def stop(self):
        with self.state_lock:
            if self.state=='stopped': 
                return
            logging.info('stop observation %s' % self.id)
            try:
                self.start_timer.cancel() # in case not started yet
                self.start_timer = None
            except AttributeError:
                pass
            if self.state=='running' and not self.dry:
                self.guppi_daq_command('STOP')
            try:
                self.process.send_signal(signal.SIGINT)
                self.process.wait()
                self.process = None
            except AttributeError:
                pass
            self.state = 'stopped'

    def is_stopped(self):
        with self.state_lock:
            return self.state=='stopped'

    def get_state(self):
        with self.state_lock:
            return self.state

    def set_timer(self):
        with self.state_lock:
            logging.info("will start obs %s at mjd=%f" % (self.id, 
                self.startMJD))
            self.start_timer = MJDTimer(self.startMJD, self.start)
            self.state = 'queued'

    def stop_at(self,mjd):
        with self.state_lock:
            # If there is already an earlier requested stop time, ignore this
            if self.stopMJD is not None:
                if mjd > self.stopMJD:
                    return
                else:
                    # kill previous stop timer, make new one
                    self.stop_timer.cancel()
                    self.stop_timer = None
            self.stopMJD = mjd
            logging.info("will stop obs %s at mjd=%f" % (self.id, self.stopMJD))
            self.stop_timer = MJDTimer(mjd, self.stop)

