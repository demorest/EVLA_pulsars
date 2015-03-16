#! /usr/bin/env python

# evla_config.py -- P. Demorest, 2015/02
#
# Code heavily based on earlier psrinfo_mcast.py by PD and S. Ransom.
#
# The main point of this part of the code is to take information from
# the vci and obs data structures (which are a literal parsing of the XML
# documents) and return relevant information in a more directly usable
# form for pulsar processing.  This includes picking out subbands that
# are configured to send VDIF to certain IP addresses, and performing
# the relevant sky frequency calculations for each.  Pulsar-related
# intents in the obs XML are parsed to recover the requested processing
# parameters as well.

import ast
import angles
from jdcal import mjd_now

class EVLAConfig(object):
    """This class defines a complete EVLA observing config, which in 
    practice means both a VCI document and OBS document have been 
    received.  Quantities relevant for pulsar processing are taken
    from the VCI and OBS and returned."""

    def __init__(self, vci=None, obs=None):
        self.set_vci(vci)
        self.set_obs(obs)

    def has_vci(self):
        return self.vci is not None

    def has_obs(self):
        return self.obs is not None

    def is_complete(self):
        return self.has_vci() and self.has_obs()

    def set_vci(self,vci):
        self.vci = vci

    def set_obs(self,obs):
        self.obs = obs
        if self.obs is None:
            self.intents = {}
        else:
            self.intents = self.parse_intents(obs.intent)

    @staticmethod
    def parse_intents(intents):
        d = {}
        for item in intents:
            k, v = item.split("=")
            if v[0] is "'" or v[0] is '"':
                d[k] = ast.literal_eval(v)
                # Or maybe we should just strip quotes?
            else:
                d[k] = v
        return d

    def get_intent(self,key,default=None):
        try:
            return self.intents[key]
        except KeyError:
            return default

    @property
    def Id(self):
        return self.obs.configId

    @property
    def datasetId(self):
        return self.obs.datasetId

    @property
    def observer(self):
        return self.get_intent("ObserverName","Unknown")

    @property
    def projid(self):
        return self.get_intent("ProjectID","Unknown")

    @property
    def scan_intent(self):
        return self.get_intent("ScanIntent","None")

    @property
    def nchan(self):
        return int(self.get_intent("PsrNumChan",32))

    @property
    def npol(self):
        return int(self.get_intent("PsrNumPol",4))

    @property
    def foldtime(self):
        return float(self.get_intent("PsrFoldIntTime",10.0))

    @property
    def foldbins(self):
        return int(self.get_intent("PsrFoldNumBins",2048))

    @property
    def timeres(self):
        return float(self.get_intent("PsrSearchTimeRes",1e-3))

    @property
    def nbitsout(self):
        return int(self.get_intent("PsrSearchNumBits",8))

    @property
    def parfile(self):
        return self.get_intent("TempoFileName",None)

    @property
    def source(self):
        return self.obs.name

    @property
    def ra_deg(self):
        return angles.r2d(self.obs.ra)

    @property
    def ra_hrs(self):
        return angles.r2h(self.obs.ra)

    @property
    def ra_str(self):
        return angles.fmt_angle(self.ra_hrs, ":", ":").lstrip('+-')

    @property
    def dec_deg(self):
        return angles.r2d(self.obs.dec)

    @property
    def dec_str(self):
        return angles.fmt_angle(self.dec_deg, ":", ":")

    @property
    def startLST(self):
        return self.obs.startLST * 86400.0

    @property
    def startTime(self):
        try:
            return float(self.obs.startTime)
        except AttributeError:
            return 0.0

    @property
    def wait_time_sec(self):
        if self.startTime==0.0:
            return None
        else:
            return 86400.0*(self.startTime - mjd_now())

    @property
    def seq(self):
        return self.obs.seq

    @property
    def telescope(self):
        return "VLA"

    def get_sslo(self,IFid):
        """Return the SSLO frequency in MHz for the given IFid.  This will
        correspond to the edge of the baseband.  Uses IFid naming convention 
        as in OBS XML."""
        for sslo in self.obs.sslo:
            if sslo.IFid == IFid:
                return sslo.freq # These are in MHz
        return None

    def get_sideband(self,IFid):
        """Return the sideband sense (int; +1 or -1) for the given IFid.
        Uses IFid naming convention as in OBS XML."""
        for sslo in self.obs.sslo:
            if sslo.IFid == IFid:
                return sslo.Sideband # 1 or -1
        return None

    def get_receiver(self,IFid):
        """Return the receiver name for the given IFid.
        Uses IFid naming convention as in OBS XML."""
        for sslo in self.obs.sslo:
            if sslo.IFid == IFid:
                return sslo.Receiver
        return None

    @staticmethod
    def swbbName_to_IFid(swbbName):
        """Converts values found in the VCI baseBand.swbbName property to
        matching values as used in the OBS sslo.IFid property. 
        
        swbbNames are like AC_8BIT, A1C1_3BIT, etc.
        IFids are like AC, AC1, etc."""

        conversions = {
                'A1C1': 'AC1',
                'A2C2': 'AC2',
                'B1D1': 'BD1',
                'B2D2': 'BD2'
                }

        (bbname, bits) = swbbName.split('_')

        if bbname in conversions:
            return conversions[bbname]

        return bbname

    def get_subbands(self,only_vdif=True,match_ips=[]):
        """Return a list of SubBand objects for all matching subbands.
        Inputs:

          only_vdif: if True, return only subbands with VDIF output enabled.
                     (default: True)
                     
          match_ips: Only return subbands with VDIF output routed to one of
                     the specified IP addresses.  If empty, all subbands
                     are returned.  non-empty match_ips implies only_vdif
                     always.
                     (default: [])
        """

        # TODO: raise an exception, or just return empty list?
        if not self.is_complete():
            raise RuntimeError("Complete configuration not available: "  
                    + "has_vci=" + self.has_vci() 
                    + " has_obs=" + self.has_obs())

        subs = []

        # NOTE, assumes only one stationInputOutput .. is this legit?
        for baseBand in self.vci.stationInputOutput[0].baseBand:
            swbbName = baseBand.swbbName
            IFid = self.swbbName_to_IFid(swbbName)
            for subBand in baseBand.subBand:
                if len(match_ips) or only_vdif:
                    # Need to get at vdif elements
                    # Not really sure what more than 1 summedArray means..
                    for summedArray in subBand.summedArray:
                        vdif = summedArray.vdif
                        if vdif:
                            if len(match_ips):
                                if (vdif.aDestIP in match_ips) or (vdif.bDestIP 
                                        in match_ips):
                                    # IPs match, add to list
                                    subs += [SubBand(subBand,self,IFid,vdif),]
                            else:
                                # No IP list specified, keep all subbands
                                subs += [SubBand(subBand,self,IFid,vdif),]
                else:
                    # No VDIF or IP list given, just keep everything
                    subs += [SubBand(subBand,self,IFid,vdif=None),]

        return subs

class SubBand(object):
    """This class defines relevant info for real-time pulsar processing
    of a single subband.  Most info is contained in the VCI subBand element,
    some is copied out for convenience.  Also the corresponding sky frequency
    is calculated, this depends on the baseBand properties, and LO settings
    (the latter only available in the OBS XML document).  Note, all frequencies
    coming out of this class are in MHz.
    
    Inputs:
        subBand: The VCI subBand element
        config:  The original EVLAConfig object
        vdif:    The summedArray.vdif VCI element (optional)
        IFid:    The IF identification (as in OBS xml)
    """

    def __init__(self, subBand, config, IFid, vdif=None):
        self.IFid = IFid
        self.swIndex = int(subBand.swIndex)
        self.sbid = int(subBand.sbid)
        self.vdif = vdif
        # Note, all frequencies are in MHz here
        self.bw = 1e-6 * float(subBand.bw)
        self.bb_center_freq = 1e-6 * subBand.centralFreq # within the baseband
        ## The (original) infamous frequency calculation, copied here
        ## for posterity:
        ##self.skyctrfreq = self.bandedge[bb] + 1e-6 * self.sideband[bb] * \
        ##                  self.subbands[isub].centralFreq
        self.sky_center_freq = config.get_sslo(IFid) \
                + config.get_sideband(IFid) * self.bb_center_freq
        self.receiver = config.get_receiver(IFid)

# Test program
if __name__ == "__main__":
    import sys
    import vcixml_parser
    import obsxml_parser
    vcifile = sys.argv[1]
    obsfile = sys.argv[2]
    print "Parsing vci='%s' obs='%s'" % (vcifile, obsfile)
    vci = vcixml_parser.parse(vcifile)
    obs = obsxml_parser.parse(obsfile)
    config = EVLAConfig(vci=vci,obs=obs)
    print "Found these subbands:"
    for sub in config.get_subbands(only_vdif=False):
        print "  IFid=%s swindex=%d sbid=%d vdif=%s bw=%.1f freq=%.1f" % (
                sub.IFid, sub.swIndex, sub.sbid, sub.vdif is not None, 
                sub.bw, sub.sky_center_freq)
