#! /usr/bin/env python

# mjd_timer.py -- P. Demorest
#
# Simple class that uses threading.Timer to start a thread at a 
# specified MJD.

import threading
from jdcal import mjd_now

class MJDTimer(object):
    """MJDTimer is based on threading.Timer, but takes a start time
    as an MJD rather than an delay in seconds.  If the start time is in
    the past, the thread will be launched immediately.  The Timer.start()
    method is called immediately when the object is created."""

    def __init__(self,mjd,function,args=[],kwargs={}):
        now = mjd_now()
        diff = (mjd - now)*86400.0
        if (diff<0.0): diff=0.0
        self.timer = threading.Timer(diff,function,args,kwargs)
        self.timer.start()

    def cancel(self):
        self.timer.cancel()
