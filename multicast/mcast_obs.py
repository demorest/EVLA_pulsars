#!/usr/bin/env python
#
# Send/receive UDP multicast packets.
# Requires that your OS kernel supports IP multicast.
#
# Usage:
#   mcast -s (sender, IPv4)
#   mcast    (receivers, IPv4)

port = 53001
group = '239.192.3.2'

from datetime import datetime
import time, struct, socket, sys
import observation_mcast

def parse_intent(intent):
    d = {}
    for item in intent:
        k, v = item.split("=")
        if v[0] is "'" or v[0] is '"':
            d[k] = eval(v)
        else:
            d[k] = v
    return d

def receiver(group, port):
    # Look up multicast group address in name server and find out IP version
    addrinfo = socket.getaddrinfo(group, None)[0]

    # Create a socket
    s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

    # Allow multiple copies of this program on one machine
    # (not strictly needed)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind it to the port
    s.bind(('', port))

    group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
    # Join group
    if addrinfo[0] == socket.AF_INET: # IPv4
        mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    else:
        mreq = group_bin + struct.pack('@I', 0)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    print "Waiting..."
    data, sender = s.recvfrom(9000)
    print datetime.now()
    data.rstrip('\0')
    return data

if __name__ == '__main__':
    while True:
        mcast_str = receiver(group, port)
        obs = observation_mcast.parseString(mcast_str)
        intent = parse_intent(obs.intent)
        print "Processed a new Observation multicast (%d bytes)..." % len(mcast_str)
        print obs.__dict__
        print intent
