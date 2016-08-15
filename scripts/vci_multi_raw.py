#! /usr/bin/env python

import sys, os
import string
from lxml import etree
from copy import deepcopy

# Read the nic config file
n_nics = {}
ips = {}
macs = {}
nic_file = os.getenv('PSR') + '/share/cbe_nics.dat'
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


vcixml = etree.parse(sys.argv[1])
vciroot = vcixml.getroot()

pfx = '{http://www.nrc.ca/namespaces/widar}'

bb = vciroot.find(pfx+'subArray').find(pfx+'stationInputOutput').find(pfx+'baseBand')
sb = bb.find(pfx+'subBand')

# Add frame delay stuff
sb.attrib['centralFreq'] = sb.attrib['centralFreq'].split('.')[0]
sb.attrib['frameSchedulingAlgorithm'] = 'setDelay'
sb.attrib['interFrameDelay'] = '400'

# Remove sb (assuming there is just one already present)
bb.remove(sb)

# List of antennas to use
# Note, this script will need fixing if the list grows beyond 16 total.
#antennas = [1, 2, 3, 4]
#antennas = [10, 12, 14, 19]
# all MJP
antennas = [6,10,12,14,18,19]
inode = 1
iblb = 0

for iant in antennas:

    #newsb = sb.copy() # not in lxml
    newsb = deepcopy(sb)

    newsb.attrib['sbid'] = str(inode-1)
    newsb.attrib['swIndex'] = str(inode)

    blb = newsb.find(pfx+'polProducts').find(pfx+'blbPair')
    blb.attrib['firstBlbPair'] = str(iblb)

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
    vdif.attrib['numBits'] = '8'
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

vcixml.write('test.xml',pretty_print=True,standalone=True,encoding='UTF-8')
