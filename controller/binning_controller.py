#! /usr/bin/env python

# binning_controller.py -- P. Demorest, 2016/10
#
# Listen for binning-mode observations, make polycos if needed, and
# start recording bin info.

import os, time
import threading
import urllib
import logging
import asyncore
from mcast_clients import ObsClient
from evla_config import EVLAConfig
from mjd_timer import MJDTimer
from jdcal import mjd_now
import tempo_utils


from optparse import OptionParser
cmdline = OptionParser()
cmdline.add_option('-v', '--verbose', dest="verbose",
        action="store_true", default=False,
        help="More verbose output")
cmdline.add_option('-l', '--listen', dest="listen",
        action="store_true", default=False,
        help="Only listen to multicast, don't launch anything") 
(opt,args) = cmdline.parse_args()

progname = 'binning_controller'

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

mjd1970 = 40587

def mjd_to_utc(mjd):
    """Given float MJD returns HH:MM:SS.S UTC string"""
    if mjd is None: return 'x'
    fmjd = mjd - int(mjd)
    h = fmjd*24.0
    m = (h-int(h))*60.0
    s = (m-int(m))*60.0
    return "%02d:%02d:%04.1f" % (int(h), int(m), s)

class CMIBQuery(object):
    """Periodically get info from the CMIB."""

    def __init__(self, startTime, dataset='X', scan='X', parfile=None):
        self.lock = threading.Lock()
        with self.lock:
            self.dataset = dataset
            self.scan = scan
            self.outdir = '/lustre/evla/pulsar/data/binning'
            self.cmib = 's006-t-0'
            self.cmib_url = 'http://%s/mah?driver=/proc/cmib/dumpTrig/phaseBin' \
                    % (self.cmib,)
            self.polys = None
            if parfile is not None:
                # Note this assumes any single scan is less than 1 hour long.
                # Have to assume something since there is no way to predict
                # scan length in advance.
                self.polys = tempo_utils.polycos.generate(parfile, 
                        site='6', mjd_start=startTime, tobs=1.0,
                        outfile='%s/%s.polyco' % (self.outdir,self.id))
            self.interval = 1.0
            self.update_rate = 15
            self._run = True
            self.startTime = startTime
            self.stopTime = None
            logging.info("will start CMIB query %s at %s" % (self.id, 
                mjd_to_utc(startTime)))
            self.start_timer = MJDTimer(startTime, self.run)
            self.stop_timer = None
            self.last_epoch = ''

    def run(self):
        logfname = '%s/%s.binlog' % (self.outdir, self.dataset)
        try:
            outf = open(logfname, 'a')
        except:
            logging.warn('%s could not open %s' % (self.id, logfname))
            outf = None
        update_count = 0
        while self._run:
            if update_count>self.update_rate:
                self.update()
                update_count = 0
            else:
                update_count += 1
            self.query(logfile=outf)
            time.sleep(self.interval)
        if outf is not None: outf.close()

    @property
    def id(self):
        return self.dataset + '.' + str(self.scan)

    @property
    def finished(self):
        with self.lock:
            return self._run == False

    def query(self,logfile=None):
        qry = urllib.urlopen(self.cmib_url).readlines()
        epoch = ''
        period1 = ''
        period2 = ''
        for l in qry:
            if l.startswith('epoch'):
                epoch = l.split()[1]
            elif l.startswith('target period') and ('Error' not in l):
                period1 = l.split()[2]
                period2 = l.split()[3]
        if (epoch != '' and epoch != self.last_epoch):
            msg = '%s %s %s %s %s' % (self.dataset, str(self.scan),
                    epoch, period1, period2)
            logging.info('query: ' + msg)
            if logfile is not None:
                logfile.write(msg + '\n')
                logfile.flush()
        self.last_epoch = epoch

    def update(self):
        if self.polys is None: 
            logging.info('update: no polycos available')
            return
        tstep = self.interval * self.update_rate
        mjd0 = mjd_now() + tstep/2.0/86400.0
        pfreq = self.polys.freq(mjd0)
        per_clk = 64.0e6 / pfreq
        time_clk = (mjd0 - mjd1970)*86400.0*64e6
        params = '%.6f %+.6f %ld' % (per_clk, 0.0, time_clk)
        logging.info('update: ' + params)
        for r in (1,2,3,4,5,6,7):
            for l in ('t','b'):
                for i in (0,1,2,3,4,5,6,7):
                    addr = 's%03d-%s-%d' % (r,l,i)
                    url = "http://%s/mah?driver=/proc/cmib/dumpTrig/pulsarModel&%s" \
                            % (addr,params)
                    urllib.urlopen(url)

    def stop(self):
        with self.lock:
            try:
                self.start_timer.cancel()
                self.start_timer = None
            except AttributeError:
                pass
            self._run = False
            # join here?

    def stop_at(self, stopTime):
        with self.lock:
            if not self._run:
                return
            if self.stopTime is not None:
                if stopTime >= self.stopTime:
                    return
                else:
                    self.stop_timer.cancel()
                    self.stop_timer = None
            self.stopTime = stopTime
            logging.info("will stop CMIB query %s at %s" % (self.id, 
                mjd_to_utc(stopTime)))
            self.stop_timer = MJDTimer(self.stopTime, self.stop)

class PhaseBinController(object):
    """Listens for OBS packets and records relevant binning info."""

    def __init__(self):
        self.vci = None
        self.queries = []

    def add_vci(self,vci):
        self.vci = vci

    def add_obs(self,obs):
        config = EVLAConfig(vci=self.vci,obs=obs)
        # Send stop to all running queries at the correct time
        for q in self.queries: q.stop_at(config.startTime)
        if config.binningPeriod != {}:
            logging.info('dataset %s scan %d period %s' % (config.datasetId,
                int(obs.scanNo), config.binningPeriod))
            if config.parfile is not None:
                logging.info('parfile %s' % config.parfile)
            # start query thread
            self.queries += [CMIBQuery(config.startTime,
                dataset=config.datasetId, 
                scan=obs.scanNo,
                parfile=config.parfile),]
        else:
            logging.info('non-binning config %s %d' % (config.datasetId,
                int(obs.scanNo)))
        # Clean all finished ones
        self.queries = [q for q in self.queries if not q.finished]
        for q in self.queries: 
            logging.debug('%s %s %s' % (q.id, mjd_to_utc(q.startTime), 
                mjd_to_utc(q.stopTime)))

    def stop_all(self):
        for q in self.queries: q.stop()
        

if __name__ == '__main__':
    # This starts the receiving/handling loop
    controller = PhaseBinController()
    obs_client = ObsClient(controller,use_configUrl=True)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        # Just exit without the trace barf
        controller.stop_all()
        logging.info('%s got SIGINT, exiting' % progname)
