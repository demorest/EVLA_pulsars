vci = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns2:subArray timeStamp="2011-11-29T05:52:02.301Z" scanId="5972313" name="TPUL0001.1" msgId="806254727" mappingOrder="5" configId="TPUL0001_sb5972311_1-new.56071.71214880787.2" activationId="TPUL0001_sb5972311_1-new.56071.71214880787.2" action="create" xmlns:ns2="http://www.nrc.ca/namespaces/widar"><ns2:listOfStations><ns2:station sid="14" name="ea14"/><ns2:station sid="13" name="ea13"/><ns2:station sid="12" name="ea12"/><ns2:station sid="11" name="ea11"/><ns2:station sid="10" name="ea10"/><ns2:station sid="28" name="ea28"/><ns2:station sid="27" name="ea27"/><ns2:station sid="26" name="ea26"/><ns2:station sid="25" name="ea25"/><ns2:station sid="23" name="ea23"/><ns2:station sid="22" name="ea22"/><ns2:station sid="21" name="ea21"/><ns2:station sid="20" name="ea20"/><ns2:station sid="8" name="ea08"/><ns2:station sid="7" name="ea07"/><ns2:station sid="6" name="ea06"/><ns2:station sid="5" name="ea05"/><ns2:station sid="3" name="ea03"/><ns2:station sid="2" name="ea02"/><ns2:station sid="1" name="ea01"/><ns2:station sid="19" name="ea19"/><ns2:station sid="18" name="ea18"/><ns2:station sid="17" name="ea17"/><ns2:station sid="16" name="ea16"/><ns2:station sid="15" name="ea15"/></ns2:listOfStations><ns2:stationInputOutput sid="all"><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="R" bbid="0"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="R" bbid="1"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="L" bbid="2"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="L" bbid="3"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="R" bbid="4"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="R" bbid="5"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="L" bbid="6"/><ns2:bbParams sourceType="FORM" sourceId="0" sideband="upper" polarization="L" bbid="7"/><ns2:baseBand swbbName="AC_8BIT" singlePhaseCenter="yes" name="A0/C0" inQuant="8" bw="1024000000" bbB="2" bbA="0"><ns2:subBand useMixer="no" swIndex="1" signalToNoise="0" sbid="0" rqNumBits="4" pulsarGatingPhase="0" mixerPhaseErrorCorr="yes" centralFreq="448000000" bw="128000000"><ns2:polProducts><ns2:pp spectralChannels="64" id="1" correlation="A*A"/><ns2:pp spectralChannels="64" id="2" correlation="A*B"/><ns2:pp spectralChannels="64" id="3" correlation="B*A"/><ns2:pp spectralChannels="64" id="4" correlation="B*B"/><ns2:blbProdIntegration recirculation="1" minIntegTime="200.0" ltaIntegFactor="2500" ccIntegFactor="2" cbeIntegFactor="3"/><ns2:blbPair quadrant="1" numBlbPairs="1" firstBlbPair="1"/><ns2:stationPacking algorithm="maxPack"/><ns2:productPacking algorithm="maxPack"/></ns2:polProducts></ns2:subBand></ns2:baseBand><ns2:baseBand swbbName="BD_8BIT" singlePhaseCenter="yes" name="B0/D0" inQuant="8" bw="1024000000" bbB="6" bbA="4"><ns2:subBand useMixer="no" swIndex="1" signalToNoise="0" sbid="0" rqNumBits="4" pulsarGatingPhase="0" mixerPhaseErrorCorr="yes" centralFreq="448000000" bw="128000000"><ns2:polProducts><ns2:pp spectralChannels="64" id="1" correlation="A*A"/><ns2:pp spectralChannels="64" id="2" correlation="A*B"/><ns2:pp spectralChannels="64" id="3" correlation="B*A"/><ns2:pp spectralChannels="64" id="4" correlation="B*B"/><ns2:blbProdIntegration recirculation="1" minIntegTime="200.0" ltaIntegFactor="2500" ccIntegFactor="2" cbeIntegFactor="3"/><ns2:blbPair quadrant="3" numBlbPairs="1" firstBlbPair="0"/><ns2:stationPacking algorithm="maxPack"/><ns2:productPacking algorithm="maxPack"/></ns2:polProducts></ns2:subBand></ns2:baseBand></ns2:stationInputOutput></ns2:subArray>"""

obs = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Observation configId="TPUL0001_sb5972311_1-new.56071.71214880787.2" seq="3552" startTime="56071.71561747685" datasetID="TPUL0001_sb5972311_1-new.56071.71214880787"><name>J0613-0200</name><ra>1.6307171161184701</ra><dec>-0.035134932283689184</dec><dra>0.0</dra><ddec>0.0</ddec><azoffs>0.0</azoffs><eloffs>0.0</eloffs><startLST>0.09083048758475343</startLST><intent>ObserverName=Bryan Butler</intent><intent>ProjectID=5972308</intent><intent>SBID=5972311</intent><intent>ScanIntent="OBSERVE_PULSAR_DEDISPERSION"</intent><intent>SBTYPE=EXPERT</intent><intent>ObsCode=TPUL0001</intent><intent>CalibratorCode=" "</intent><scanNo>3</scanNo><subscanNo>1</subscanNo><correlator>widar</correlator><sslo Sideband="1" IFid="AC" Receiver="1.5GHz"><freq>880.0</freq></sslo><sslo Sideband="1" IFid="BD" Receiver="1.5GHz"><freq>1008.0</freq></sslo></Observation>"""
