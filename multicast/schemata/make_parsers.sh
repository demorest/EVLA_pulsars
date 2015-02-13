# NOTE, updated xsd files can be found at
# http://www.aoc.nrao.edu/asg/widar/schemata/
generateDS.py --silence -o observation_mcast.py Observation.xsd
generateDS.py --silence -o vcirequest_mcast.py vci/vciRequest.xsd
perl -p -i -e 's/""""""//' vcirequest_mcast.py
perl -p -i -e 's/"""""//' vcirequest_mcast.py
perl -p -i -e 's/""""/" """/' vcirequest_mcast.py
