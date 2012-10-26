import angles

class subband:

    def __init__(self, subBand):
        self.swIndex = subBand.swIndex
        self.sbid = subBand.sbid
        self.bw = float(subBand.bw)
        self.centralFreq = subBand.centralFreq
        self.summedArray = subBand.summedArray

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
        if hasattr(o, 'startMJD'):
            self.startMJD = o.startMJD
        else:
            self.startMJD = 0.0
        self.seq = o.seq
        self.telescope = "EVLA"
        self.backend = "YUPPI"
        self.receiver = o.sslo[0].Receiver
        self.sideband = o.sslo[0].Sideband
        self.bandedge = o.sslo[0].freq

    def parse_vci(self):
        v = self.vci
        nsIOs = len(v.stationInputOutput)
        sIO = v.stationInputOutput[0]
        nBBs = len(sIO.baseBand)
        BB = sIO.baseBand[0]
        nSBs = len(BB.subBand)
        self.subbands = [subband(x) for x in BB.subBand]
        print "Found %d station IOs, %d basebands, and %d subbands" % \
              (nsIOs, nBBs, nSBs)

    def parse(self):
        self.parse_obs()
        self.parse_vci()
        # Might need a list of these...  this assumes 1 subband
        self.bandwidth = 1e-6 * self.sideband * self.subbands[0].bw # in MHz
        self.skyctrfreq = self.bandedge + 1e-6 * self.sideband * \
                          self.subbands[0].centralFreq  # in MHz

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
