import angles

def get_val(d,key,default=None):
    try:
        return d[key]
    except KeyError:
        return default

class subband:

    def __init__(self, subBand, vdif=None, BBname=""):
        self.swIndex = subBand.swIndex
        self.sbid = subBand.sbid
        self.bw = float(subBand.bw)
        self.centralFreq = subBand.centralFreq
        self.summedArray = subBand.summedArray
        self.vdif = vdif
        self.baseBandName = BBname

class EVLA_config:
    
    def parse_obs_intent(self, intent):
        d = {}
        for item in intent:
            k, v = item.split("=")
            if v[0] is "'" or v[0] is '"':
                d[k] = eval(v)
            else:
                d[k] = v
        return d

    def parse_vci_subbands(self, intent):
        d = {}
        for item in intent:
            k, v = item.split("=")
            if v[0] is "'" or v[0] is '"':
                d[k] = eval(v)
            else:
                d[k] = v
        return d

    def parse_obs(self):
        o = self.obs
        intent = self.parse_obs_intent(o.intent)
        self.observer = get_val(intent,"ObserverName","Unknown")
        self.projid = get_val(intent,"ProjectID","Unknown")
        self.scan_intent = get_val(intent,"ScanIntent","None")
        # TODO what about checking bounds on some of these...
        self.nchan = int(get_val(intent,"PsrNumChan",32))
        self.npol = int(get_val(intent,"PsrNumPol",4))
        self.foldtime = float(get_val(intent,"PsrFoldIntTime",10.0))
        self.foldbins = int(get_val(intent,"PsrFoldNumBins",2048))
        self.timeres = float(get_val(intent,"PsrSearchTimeRes",1e-3))
        self.nbitsout = int(get_val(intent,"PsrSearchNumBits",8))
        self.parfile = get_val(intent,"TempoFileName",None)
        self.source = o.name
        self.ra_deg = angles.r2d(o.ra)
        self.ra_hrs = angles.r2h(o.ra)
        self.ra_str = angles.fmt_angle(self.ra_hrs, ":", ":").lstrip('+-')
        self.dec_deg = angles.r2d(o.dec)
        self.dec_str = angles.fmt_angle(self.dec_deg, ":", ":")
        self.startLST = o.startLST * 86400.0
        if hasattr(o, 'startTime'):
            self.startMJD = float(o.startTime)
        else:
            self.startMJD = 0.0
        self.seq = o.seq
        self.telescope = "VLA"
        self.backend = "YUPPI"
        # Do these ever vary with IF??
        self.receiver = o.sslo[0].Receiver
        self.bandedge = {}
        self.sideband = {}
        for s in o.sslo:
            self.bandedge[s.IFid] = s.freq
            self.sideband[s.IFid] = s.Sideband

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
