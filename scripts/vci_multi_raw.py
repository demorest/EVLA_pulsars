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
        default="1,3,5,6,9,10,11,12,13,14,18,19,23,27")
par.add_argument("-r", "--remove-ant",
        help="Remove the specified antenna from the list",
        default=[], action="append",type=int)
args = par.parse_args()

# Read the nic config file
n_nics = {}
ips = {}
macs = {}
if os.getenv('PSR') is not None:
    nic_file = os.getenv('PSR') + '/share/cbe_nics.dat'
else:
    nic_file = os.path.dirname(os.path.abspath(__file__)) + '/cbe_nics.dat'
for l in open(nic_file).readlines():
    if l.startswith('#'): continue
    (node,nic,ip,mac) = l.split()
    if n_nics.has_key(node):
        n_nics[node] += 1
    else:
        n_nics[node] = 1
    key = '%s-%s' % (node, nic.replace('p2p',''))
    ips[key] = ip
    macs[key] = mac

vcixml = etree.parse(args.vcifile)
vciroot = vcixml.getroot()

pfx = '{http://www.nrc.ca/namespaces/widar}'

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

# List of antennas to use
antennas = map(int,args.ants.split(','))

for a in args.remove_ant:
    try:
        antennas.remove(a)
    except ValueError:
        pass

inode = 1
iblb = 0
for iant in antennas:

    #newsb = sb.copy() # not in lxml
    newsb = deepcopy(sb)

    newsb.attrib['sbid'] = str(inode-1)
    newsb.attrib['swIndex'] = str(inode)

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
    node = 'cbe-node-%02d' % inode
    nic1 = node + '-1'
    nic2 = node + '-2'

    vdif.attrib['agcEnabled'] = 'false'
    vdif.attrib['vdifEnableB'] = 'true'
    vdif.attrib['vdifEnableA'] = 'true'
    vdif.attrib['aPacketDelay'] = '0'
    vdif.attrib['bPacketDelay'] = '0'
    vdif.attrib['numBits'] = '4'
    vdif.attrib['frameSize'] = '1250'
    vdif.attrib['epochOffset'] = '127057024'
    vdif.attrib['epoch'] = '0'
    vdif.attrib['bThread'] = '1'
    vdif.attrib['aThread'] = '0'

    vdif.attrib['stationId'] = str(12300 + iant)
    vdif.attrib['aDestIP'] = ips[nic1]
    vdif.attrib['bDestIP'] = ips[nic2]
    vdif.attrib['aDestMAC'] = macs[nic1]
    vdif.attrib['bDestMAC'] = macs[nic2]
    vdif.attrib['aDestPort'] = '50000'
    vdif.attrib['bDestPort'] = '50000'

    bb.append(newsb)

    inode += 1
    iblb += 1

vcixml.write(sys.stdout,pretty_print=True,standalone=True,encoding='UTF-8')
