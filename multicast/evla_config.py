import ast
import angles

class subband:

    def __init__(self, subBand, vdif=None, BBname=""):
        self.swIndex = subBand.swIndex
        self.sbid = subBand.sbid
        self.bw = float(subBand.bw)
        self.centralFreq = subBand.centralFreq
        self.summedArray = subBand.summedArray
        self.vdif = vdif
        self.baseBandName = BBname

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
    def observer(self):
        return self.get_intent("ObserverName","Unknown")

    @property
    def projid(self):
        return self.getintent("ProjectID","Unknown")

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
        return = int(self.get_intent("PsrSearchNumBits",8))

    @property
    def parfile(self):
        return get_intent("TempoFileName",None)

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
    def seq(self):
        return self.obs.seq

    @property
    def telescope(self):
        return "VLA"

    @property
    def backend(self):
        return "YUPPI"


        # Do these ever vary with IF??
        #self.receiver = o.sslo[0].Receiver
        #self.bandedge = {}
        #self.sideband = {}
        #for s in o.sslo:
        #    self.bandedge[s.IFid] = s.freq
        #    self.sideband[s.IFid] = s.Sideband

    def parse_vci(self,match_ips=[]):
        v = self.vci
        nsIOs = len(v.stationInputOutput)
        sIO = v.stationInputOutput[0]
        nBBs = len(sIO.baseBand)
        # Grab only matching subbands
        self.subbands = []
        nSBs = 0
        for BB in sIO.baseBand:
            nSBs += len(BB.subBand)
            bbname = BB.swbbName.split('_')[0]
            if bbname=="A1C1": bbname="AC1"
            if bbname=="A2C2": bbname="AC2"
            if bbname=="B1D1": bbname="BD1"
            if bbname=="B2D2": bbname="BD2"
            if len(match_ips)==0:
                self.subbands += [subband(x, BBname=BB.bbname) 
                        for x in BB.subBand]
            else:
                for sb in BB.subBand:
                    for sa in sb.summedArray:
                        if sa.vdif:
                            v = sa.vdif
                            if (v.aDestIP in match_ips) or (v.bDestIP 
                                    in match_ips):
                                self.subbands += [subband(sb,vdif=v,
                                    BBname=bbname)]
        print "Found %d station IOs, %d basebands, and %d total subbands" % \
              (nsIOs, nBBs, nSBs)
        if len(match_ips):
            print "Found %d matching subbands" % (len(self.subbands))

    def parse(self,match_ips=[]):
        self.parse_obs()
        self.parse_vci(match_ips)
        # Might need a list of these...  this assumes 1 subband
        if len(self.subbands)>0:
            isub = 0
            bb = self.subbands[isub].baseBandName
            # Note, subbands are _always_ USB regardless of overall sense.
            # Old (wrong) version):
            #self.bandwidth = 1e-6 * self.sideband[bb] * self.subbands[isub].bw
            # Both results should be MHz:
            self.bandwidth = 1e-6 * self.subbands[isub].bw
            self.skyctrfreq = self.bandedge[bb] + 1e-6 * self.sideband[bb] * \
                              self.subbands[isub].centralFreq

if __name__ == "__main__":
    g = guppi_status()
    g.show()

    print
    print 'keys:', g.keys()
    print
    print 'values:', g.values()
    print
    print 'items:', g.items()
    print
