#! /usr/bin/env python

# Simple pyro daemon that will publish the current guppi_status and 
# other basic info

import os
import Pyro4
import errno
import socket
import time
from guppi_daq.guppi_utils import guppi_status

print "yuppi_status_daemon started at", time.ctime()

# Class to collect various node status info.
# We will not use a persistent connection to guppi_status because
# I want this to keep running even when the node is unconfigured/busted.
class yuppi_node_status:

    def __init__(self):
        self.n_daq = 4 
        self.shmem_keys = [None,] * self.n_daq
        self.processes = []

    def update(self):
        for i in range(self.n_daq):
            self.update_shmem_keys(idx=i)
        self.update_processes()

    def get_shmem_keys(self,idx=0):
        return self.shmem_keys[idx]

    def update_shmem_keys(self,idx=0):
        try:
            g = guppi_status(doread=False,idx=idx)
            g.tryread()
            self.shmem_keys[idx] = dict(zip(g.hdr.keys(),g.hdr.values()))
        except:
            # Need to separate different types of errors?
            self.shmem_keys[idx] = None

    def update_processes(self):
        # TODO do something with ps to get the processes we want
        self.processes = []

Pyro4.config.SERVERTYPE = 'multiplex'
Pyro4.config.HMAC_KEY='blahblahblah'
stat = yuppi_node_status()
# Retry until connected, this waits for the previous copy of the
# process to exit.
daemon = None
while daemon==None:
    try:
        daemon = Pyro4.Daemon(host=os.uname()[1],port=50100)
    except socket.error, v:
        errcode = v[0]
        if errcode==errno.EADDRINUSE:
            pass
        else:
            raise 
uri = daemon.register(stat,objectId="yuppi_status")
print uri
daemon.requestLoop()

