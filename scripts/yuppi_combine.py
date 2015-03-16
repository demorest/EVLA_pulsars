#! /usr/bin/env python

import os,sys,glob
import logging
import psrchive
from collections import namedtuple

from optparse import OptionParser
cmdline = OptionParser(usage='usage: %prog [options] scan_prefix')
cmdline.add_option('-v', '--verbose', dest='verbose', action='store_true',
        default=False, help='Verbose logging')
cmdline.add_option('-b', '--bb', dest='bb', action='store',
        default='AC', help='Baseband (IF) to process [%default]')
cmdline.add_option('-i', '--idx', dest='idx', action='store',
        type='int', default=0, help='Starting subint index [%default]')
cmdline.add_option('-n', '--nsub', dest='nsub', action='store',
        type='int', default=128, help='Number of subints to add [%default]')
cmdline.add_option('-d', '--subdir', dest='dir', action='store',
        default='cbe-node-??', help='Directory (glob) with data files [%default]')
(opt,args) = cmdline.parse_args()

if len(args)!=1:
    cmdline.print_help()
    sys.exit(0)

loglevel = logging.INFO
if opt.verbose:
    loglevel = logging.DEBUG

# Include pid to distinguish different instances
pid = '%5d' % os.getpid()
logging.basicConfig(format="%(asctime)-15s " + pid
        +" %(levelname)8s %(message)s", level=loglevel)

# These things will be command line options:
#scan = '15A-105_sb30474261_1_test.57093.660558020834.963.J1909-3744'
scan = args[0]
baseband = opt.bb
idx0 = opt.idx
idx1 = opt.idx + opt.nsub

# Example filename:
# 15A-105_sb30474261_1_test.57093.660558020834.963.J1909-3744.BD-15_0029.ar
class FileInfo(namedtuple('FileInfo','path fname scan ifid sbid idx ext')):
    def __new__(cls, fname_path):
        (path,fname) = os.path.split(fname_path)
        (tmp,ext) = os.path.splitext(fname)
        ext = ext.strip('.')
        (scan,tmp) = os.path.splitext(tmp)
        tmp = tmp.strip('.')
        (ifsb,idx) = tmp.split('_')
        (ifid,sbid) = ifsb.split('-')
        return super(FileInfo,cls).__new__(cls, path, 
                fname, scan, ifid,
                sbid, idx, ext)

fname_base = '%s/%s' % (opt.dir,scan)
fnames = glob.glob(fname_base + '.*.ar') + glob.glob(fname_base+'.*.cf')

sub_files = {}
ext = 'ar'
for fname in fnames:
    info = FileInfo(fname)
    subband = info.ifid + '-' + info.sbid
    ext = info.ext # TODO check for mismatched extensions

    # Skip files that are not from the baseband or subint we want
    if info.ifid != baseband:
        continue
    if int(info.idx)<idx0 or int(info.idx)>=idx1:
        continue

    # build list of files per subband
    if subband in sub_files.keys():
        sub_files[subband].append(fname)
    else:
        sub_files[subband] = [fname,]

subbands = sub_files.keys()
nfiles = 0
for sub in subbands:
    nfiles += len(sub_files[sub])

logging.info('Found %s subbands, %d files' % (len(subbands), nfiles))
if nfiles==0:
    logging.info('No matching files, exiting')
    sys.exit(0)

timeappend = psrchive.TimeAppend()
timeappend.chronological = True

# First combine each subband set into a single archive
sub_arch = {}
for subband in sorted(subbands):
    logging.debug("Reading subband %s" % subband)
    first = True
    # Assume name sort will ensure time order, this could be changed
    # to read times from files since we need read all of them anyways.
    for fname in sorted(sub_files[subband]):
        if first:
            sub_arch[subband] = psrchive.Archive_load(fname)
            timeappend.init(sub_arch[subband])
            first = False
        else:
            timeappend.append(sub_arch[subband], psrchive.Archive_load(fname))

# Now combine subbands into the final archive
logging.debug("Combining all subbands")
freqappend = psrchive.FrequencyAppend()
patch = psrchive.PatchTime()
basearch = sub_arch[subbands[0]]
freqappend.init(basearch)
# TODO this could fail if the first subband was truncated relative to 
# the others so its polycos do not span the full observation.  Could
# be improved by selecting whichever subband has the longest timespan.
freqappend.ignore_phase = True
if ext!='cf':
    polycos = basearch.get_model()
else:
    polycos = None
for sub in subbands[1:]:
    if polycos is not None: 
        sub_arch[sub].set_model(polycos)
    patch.operate(basearch,sub_arch[sub])
    freqappend.append(basearch,sub_arch[sub])

# Make sure .cf files get marked as cals
if ext=='cf':
    basearch.set_type('PolnCal')

outfname = '%s.%s_%d.%s' % (scan, baseband, idx0, ext)
logging.info("Unloading '%s'" % outfname)
basearch.unload(outfname)
logging.debug("Done")