# NOTE, updated xsd files can be found at
# http://www.aoc.nrao.edu/asg/widar/schemata/
generateDS.py --silence -o ../obsxml_parser.py Observation.xsd
generateDS.py --silence -o ../vcixml_parser.py vci/vciRequest.xsd
# These seem not necessary with newer versions of generateDS:
perl -p -i -e 's/""""""//' ../vcixml_parser.py
perl -p -i -e 's/"""""//' ../vcixml_parser.py
perl -p -i -e 's/""""/" """/' ../vcixml_parser.py
