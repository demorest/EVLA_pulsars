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
        try:
            self.observer = intent["ObserverName"]
        except:
            self.observer = "Unknown"
        try:
            self.projid = intent["ProjectID"]
        except:
            self.projid = "Unknown"
        try:
            self.scan_intent = intent["ScanIntent"]
        except:
            self.scan_intent = "None"
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
        self.sideband = o.sslo[0].Sideband
        self.bandedge = {}
        for s in o.sslo:
            self.bandedge[s.IFid] = s.freq

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
            if len(match_ips)==0:
                self.subbands += [subband(x,BBname=BB.swbbName[:2]) 
                        for x in BB.subBand]
            else:
                for sb in BB.subBand:
                    for sa in sb.summedArray:
                        if sa.vdif:
                            v = sa.vdif
                            if (v.aDestIP in match_ips) or (v.bDestIP 
                                    in match_ips):
                                self.subbands += [subband(sb,vdif=v,
                                    BBname=BB.swbbName[:2])]
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
            # Both results should be MHz:
            self.bandwidth = 1e-6 * self.sideband * self.subbands[isub].bw
            self.skyctrfreq = self.bandedge[bb] + 1e-6 * self.sideband * \
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
