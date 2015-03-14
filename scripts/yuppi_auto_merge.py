#! /usr/bin/env python

import os,sys,glob
import logging
import psrchive
from collections import namedtuple

from optparse import OptionParser
cmdline = OptionParser(usage='usage: %prog [options] scan_prefix')
cmdline.add_option('-v', '--verbose', dest='verbose', action='store_true',
        default=False, help='Verbose logging')
cmdline.add_option('-d', '--subdir', dest='dir', action='store',
        default='cbe-node-??', help='Directory with data files [%default]')
(opt,args) = cmdline.parse_args()


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
        all_files += glob.glob('%s/*.%s' % (subdir,ext))
    scans = {}
    for fname in all_files:
        info = FileInfo(fname)
        if info.scan not in scans.keys(): scans[info.scan] = ScanInfo()
        scans[info.scan].add_file(fname)
    return scans

scans = get_scans(opt.dir)

for scan in scans.keys():
    print (scan, scans[scan].nfiles, scans[scan].idx0, scans[scan].idx1,
            scans[scan].max_filesize/(2.0**20),
            scans[scan].total_filesize / (2.0**20),
            scans[scan].ifids)

