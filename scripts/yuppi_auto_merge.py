#! /usr/bin/env python

import os,sys,glob
from math import log
import logging
import psrchive
from collections import namedtuple

# TODO:
#  - make this a persistent process, watching for new files
#    (need to decide scheme for figuring out when a scan is done)
#  - decide if multiple merging processes should be run in parallel
#    or if sequential calls are fine.

from optparse import OptionParser
cmdline = OptionParser(usage='usage: %prog [options] scan_prefix')
cmdline.add_option('-v', '--verbose', dest='verbose', action='store_true',
        default=False, help='Verbose logging')
cmdline.add_option('-d', '--subdir', dest='dir', action='store',
        default='cbe-node-??', help='Directory (glob) with data files [%default]')
cmdline.add_option('-B', '--combine-ifs', dest='all_bb', action='store_true',
        default=False, 
        help='Combine different basebands into single file [%default]')
(opt,args) = cmdline.parse_args()

try:
    scan_prefix = args[0]
except IndexError:
    scan_prefix = ''

loglevel = logging.INFO
if opt.verbose:
    loglevel = logging.DEBUG

logging.basicConfig(format="%(asctime)-15s %(levelname)8s %(message)s", level=loglevel)

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

class ScanInfo(object):
    """Simple class to contain basic info about the files that make up
    a scan."""

    def __init__(self):
        self.idx0 = -1
        self.idx1 = -1
        self.nfiles = 0
        self.max_filesize = 0
        self.total_filesize = 0
        self.ifids = []

    def add_file(self,fname):
        info = FileInfo(fname)
        idx = int(info.idx)
        size = os.path.getsize(fname)
        if self.idx0==-1 or idx<self.idx0: self.idx0 = idx
        if idx>self.idx1: self.idx1 = idx
        if size > self.max_filesize: self.max_filesize = size
        self.total_filesize += size
        self.nfiles += 1
        if info.ifid not in self.ifids: self.ifids.append(info.ifid)

# Get the list of unique scans, returns a dict of ScanInfo objects
def get_scans(subdir):
    all_files = []
    # File extensions to process
    exts = ['ar','cf']
    for ext in exts:
        all_files += glob.glob('%s/%s*.%s' % (subdir,scan_prefix,ext))
    scans = {}
    for fname in all_files:
        try:
            info = FileInfo(fname)
        except ValueError:
            logging.debug("Error parsing filename '%s'" % fname)
            continue
        if info.scan not in scans.keys(): scans[info.scan] = ScanInfo()
        scans[info.scan].add_file(fname)
    return scans

def get_scans2(subdir):
    all_files = []
    subdirs = ['cbe-node-%02d'%i for i in range(1,17)]
    for d in subdirs:
        #print(d)
        for f in os.listdir(d):
            if (f.endswith('.ar') or f.endswith('.cf')) and (f.startswith(scan_prefix)):
                mjd = int(f.split('.')[-6])
                if mjd>60200:
                    all_files.append(d+'/'+f)
    scans = {}
    for fname in all_files:
        #print(fname)
        try:
            info = FileInfo(fname)
        except ValueError:
            logging.debug("Error parsing filename '%s'" % fname)
            continue
        if info.scan not in scans.keys(): scans[info.scan] = ScanInfo()
        scans[info.scan].add_file(fname)
    return scans

#scans = get_scans(opt.dir)
scans = get_scans2(opt.dir)

for scan in scans.keys():
    info = scans[scan]
    if opt.verbose:
        print (scan, info.nfiles, info.idx0, info.idx1,
                info.max_filesize/(2.0**20),
                info.total_filesize / (2.0**20),
                info.ifids)
    # Split so that we have ~1GB output files per scan, in 2^N sized 
    # groups of subints.
    nparts = int(info.total_filesize/float(len(info.ifids))/float(1<<31)) + 1
    nsub = info.idx1 - info.idx0 + 1
    if nparts==1:
        subints_per_part = nsub
    else:
        subints_per_part = 1<<int(log(float(nsub)/nparts,2.0))
    if opt.verbose: 
        print "nsub=%d, nparts=%d, subints_per_part=%d" % (nsub,nparts,
                subints_per_part)
    outidx = 1
    for isub in range(info.idx0,info.idx1+1,subints_per_part):
        if opt.all_bb: bblist = ['all',]
        else: bblist = info.ifids
        for bb in bblist:
            # TODO check whether output file exists
            outdir = 'merged_data'
            cmd = 'nice -n20 yuppi_combine.py'
            cmd += ' -v'
            cmd += ' -b%s' % bb
            cmd += ' -i%d' % isub
            cmd += ' -n%d' % subints_per_part
            cmd += " -d'%s'" % opt.dir
            cmd += ' -x%d' % outidx
            cmd += ' -o%s' % outdir
            cmd += ' ' + scan
            print cmd
        outidx += 1
        sys.stdout.flush()

