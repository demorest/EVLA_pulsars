#! /usr/bin/env python

# Convert bin axis into extra spectral windows to fool
# CASA/etc into letting us look at phase-binned data.
# Needs to be run from inside the SDM directory, and
# nbins needs to be set by hand below.  Needs same number of 
# bins to be used in all scans in the dataset.

import os, sys
from lxml import etree

def xmlname(table):
    return table + '.xml'

def write_xml(tree,fname):
    tree.write(fname,xml_declaration=True,encoding='UTF-8',
            standalone=True)

# These tables have per-SPW entries that need to be expanded:
tables_to_expand = ['CalDevice', 'DataDescription', 'Feed', 
        'Receiver', 'Source', 'SpectralWindow']

# The main ASDM.xml file that lists numbers of rows
asdm = etree.parse(xmlname('ASDM'))

# number of phase bins
nbin = 40

data_descripts = []

for table in tables_to_expand:
    table_tree = etree.parse(xmlname(table))
    table_root = table_tree.getroot()

    if table=='DataDescription':
        dd_id = 0

    # Loop through table rows, create new row defs
    xml_to_add = []
    elem_to_remove = []
    for row in table_tree.iter('row'):
        spw_id = row.find('spectralWindowId')
        # Assume these are of the form SpectralWindow_0
        orig_id = int(spw_id.text.split('_')[1])
        if table=='SpectralWindow': 
            name = row.find('name')
            orig_name = name.text
            freq = row.find('chanFreqStart')
            orig_freq = float(freq.text)
        if table=='DataDescription':
            pol_id = row.find('polOrHoloId').text
        for ibin in range(nbin):
            new_id = orig_id*nbin + ibin
            spw_id.text = 'SpectralWindow_%d' % new_id
            if table=='SpectralWindow':
                name.text = orig_name + '#P%d' % ibin
                freq.text = '%.11E' % (orig_freq + float(ibin))
            if table=='DataDescription':
                dd_text = 'DataDescription_%d' % dd_id
                row.find('dataDescriptionId').text = dd_text
                if pol_id=='Polarization_0':
                    data_descripts.append(dd_text)
                dd_id += 1
            xml_to_add.append(etree.tostring(row))
        elem_to_remove.append(row)

    # Remove the old rows
    for row in elem_to_remove:
        table_root.remove(row)

    # Add the new rows
    for xml in xml_to_add:
        table_root.append(etree.fromstring(xml))

    # Write the updated table
    write_xml(table_tree, table+'.xml')

    # Update NumberRows entry in ASDM.xml
    for asdm_t in asdm.iter('Table'):
        if asdm_t.find('Name').text == table:
            nrows = asdm_t.find('NumberRows')
            new_rows = int(nrows.text) * nbin
            nrows.text = str(new_rows)

# ConfigDescription refers to DataDescription
config_tree = etree.parse(xmlname('ConfigDescription'))
dd_text = '1 %d' % len(data_descripts)
sw_text = '1 %d' % len(data_descripts)
for dd in data_descripts: 
    dd_text += ' ' + dd
    sw_text += ' SwitchCycle_0'
for row in config_tree.iter('row'):
    row.find('dataDescriptionId').text = dd_text
    row.find('switchCycleId').text = sw_text
write_xml(config_tree, 'ConfigDescription.xml')

# Write out ASDM.xml
write_xml(asdm,'ASDM.xml')

########### Mess with the BDFs
import glob
#import email
bdfs = glob.glob('ASDMBinary/*')

# Return a tuple containing (mime_header_string, xml header string, 
# rest of file).  The BDFs sometimes seem to break python's email
# package, this is a workaround with that.
def bdf_split(fname):
    f = open(fname)
    first = ""
    xml = ""
    rest = ""
    gotit = False
    while not gotit:
        l = f.readline()
        if l.startswith('<sdmDataHeader '):
            xml = l
            gotit = True
        else:
            first += l
    rest = f.read()
    return (first,xml,rest)

for bdf_name in bdfs:
    print "Updating BDF '%s'" % bdf_name
    #bdf = email.message_from_file(open(bdf_name,'r'))
    #hdr = bdf.get_payload(0)
    #hdr_tree = etree.fromstring(hdr.get_payload())
    (bdf_start, hdr_string, bdf_end) = bdf_split(bdf_name)
    hdr_tree = etree.fromstring(hdr_string)
    pfx = '{' + hdr_tree.nsmap[None] + '}'
    # Iterate over spectralwindow tags
    for spw in hdr_tree.iter(pfx+'spectralWindow'):
        orig_swidx = int(spw.attrib['sw'])
        spw.attrib['numBin'] = '1'
        spw_str = etree.tostring(spw)
        for ibin in range(nbin):
            swidx = (orig_swidx-1)*nbin + ibin + 1
            if ibin==0:
                spw.attrib['sw'] = '%d' % swidx
                last_spw = spw
            else:
                spw_new = etree.fromstring(spw_str)
                spw_new.attrib['sw'] = '%d' % swidx
                last_spw.addnext(spw_new)
                last_spw = spw_new
    #hdr.set_payload(etree.tostring(hdr_tree, xml_declaration=True,
    #    encoding='UTF-8', standalone=True))
    #open(bdf_name,'w').write(bdf.as_string())
    hdr_string = etree.tostring(hdr_tree,xml_declaration=False) + '\n'
    fout = open(bdf_name,'w')
    fout.write(bdf_start)
    fout.write(hdr_string)
    fout.write(bdf_end)
    fout.close()

