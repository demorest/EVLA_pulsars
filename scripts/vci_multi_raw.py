#! /usr/bin/env python

import sys, os
import string
from lxml import etree
from copy import deepcopy
import argparse

par = argparse.ArgumentParser()
par.add_argument("vcifile", help="Input VCI file")
par.add_argument("-a", "--ants", 
        help="Comma-separated list of antennas to use [default='%(default)s']",
        default="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28")
par.add_argument("-r", "--remove-ant",
        help="Remove the specified antenna from the list",
        default=[], action="append",type=int)
par.add_argument("-b", "--nbits",
        help="Number of bits to use for VDIF output [default=%(default)d]",
        type=int, default=4)
args = par.parse_args()

# Read the nic config file
n_nics = {}
n_used = {}
ips = {}
macs = {}
if os.getenv('PSR') is not None:
    nic_file = os.getenv('PSR') + '/share/cbe_nics.dat'
else:
    nic_file = os.path.dirname(os.path.abspath(__file__)) + '/cbe_nics.dat'
for l in open(nic_file).readlines():
    if l.startswith('#'): continue
    (node,nic,ip,mac) = l.split()
    if not n_nics.has_key(node):
        n_nics[node] = 0
        n_used[node] = 0
        ips[node] = []
        macs[node] = []
    n_nics[node] += 1
    ips[node].append(ip)
    macs[node].append(mac)

nodes = sorted(n_nics.keys())

vcixml = etree.parse(args.vcifile)
vciroot = vcixml.getroot()

pfx = '{http://www.nrc.ca/namespaces/widar}'

# List of antennas to use
antennas = map(int,args.ants.split(','))
for a in args.remove_ant:
    try:
        antennas.remove(a)
    except ValueError:
        pass

# Make sure we have one ant per node
if len(antennas)>2*len(nodes):
    raise RuntimeError("Number of antennas (%d) greater than 2x number of nodes (%d)" % 
            (len(antennas), len(nodes)))

# Check that it only has one subband and one baseband
sio = vciroot.find(pfx+'subArray').find(pfx+'stationInputOutput')

nbbs = len(sio.findall(pfx+'baseBand'))
if nbbs>1:
    raise RuntimeError("Input VCI file must have only one baseband")
bb = sio.find(pfx+'baseBand')

nsbs = len(bb.findall(pfx+'subBand'))
if nbbs>1:
    raise RuntimeError("Input VCI file must have only one subband")
sb = bb.find(pfx+'subBand')

# Add frame delay stuff
sb.attrib['centralFreq'] = sb.attrib['centralFreq'].split('.')[0]
sb.attrib['frameSchedulingAlgorithm'] = 'setDelay'
sb.attrib['interFrameDelay'] = '400'

# Remove existing subband section
bb.remove(sb)

# If more than 16 antennas we need to add another baseband section
if len(antennas)>16:
    bb2 = deepcopy(bb)
    bb2.attrib['bbA'] = str(int(bb2.attrib['bbA']) + 1)
    bb2.attrib['bbB'] = str(int(bb2.attrib['bbB']) + 1)
    sio.append(bb2)

inode = 0
iblb = 0
nant = 0
inic = 0
iport = 0
for iant in antennas:

    #newsb = sb.copy() # not in lxml
    newsb = deepcopy(sb)

    newsb.attrib['sbid'] = str((nant) % 16)
    newsb.attrib['swIndex'] = str(nant+1)

    blb = newsb.find(pfx+'polProducts').find(pfx+'blbPair')
    blb.attrib['quadrant'] = str((iblb/16)+1)
    blb.attrib['firstBlbPair'] = str(iblb%16)
    blb.attrib['numBlbPairs'] = '1'

    sa = newsb.find(pfx+'summedArray')
    sa.attrib['sid'] = str(iant+100)
    exclude = set(range(1,29))
    exclude.remove(iant)
    sa.attrib['excludeStations'] = string.join(map(str,exclude))

    vdif = sa.find(pfx+'vdif')
    vdif.clear()
    node = nodes[inode]

    vdif.attrib['agcMode'] = 'setRms'
    vdif.attrib['vdifEnableB'] = 'true'
    vdif.attrib['vdifEnableA'] = 'true'
    vdif.attrib['aPacketDelay'] = '0'
    vdif.attrib['bPacketDelay'] = '0'
    vdif.attrib['numBits'] = '%d' % args.nbits
    vdif.attrib['frameSize'] = '1250'
    vdif.attrib['epochOffset'] = '127057024'
    vdif.attrib['epoch'] = '0'
    vdif.attrib['bThread'] = '1'
    vdif.attrib['aThread'] = '0'

    vdif.attrib['stationId'] = str(12300 + iant)
    vdif.attrib['aDestIP'] = ips[node][inic+0]
    vdif.attrib['bDestIP'] = ips[node][inic+1]
    vdif.attrib['aDestMAC'] = macs[node][inic+0]
    vdif.attrib['bDestMAC'] = macs[node][inic+1]
    destport = '%d' % (50000 + iport)
    vdif.attrib['aDestPort'] = destport
    vdif.attrib['bDestPort'] = destport

    if nant<16:
        bb.append(newsb)
    else:
        bb2.append(newsb)

    inode += 1
    if inode >= len(nodes):
        inode -= len(nodes)
        inic += 2
        iport += 1
    iblb += 1
    nant += 1

vcixml.write(sys.stdout,pretty_print=True,standalone=True,encoding='UTF-8')
