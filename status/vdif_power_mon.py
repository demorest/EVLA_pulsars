#! /usr/bin/env python2.7

import sys
import numpy
from guppi_daq.guppi_utils import guppi_status, guppi_databuf

class yuppi_power_mon:

    def __init__(self,timespan=300.,nbytes_sum=2048):
        self.timespan = timespan # In sec
        self.nbytes_sum = nbytes_sum
        self.time = []
        self.pow0 = []
        self.pow1 = []
        self.make_luts()
        self.lut_pow = self.lut_pow_8bit # Default to 8-bit

    def make_luts(self):
        # Make power look up tables for 8 and 2 bit data
        self.lut_pow_8bit = numpy.zeros(256)
        self.lut_pow_4bit = numpy.zeros(256)
        self.lut_pow_2bit = numpy.zeros(256)
        for i in range(256):
            self.lut_pow_8bit[i] = (float(i)-127.5)**2
        # Make zero not cause big spikes
        self.lut_pow_8bit[0] = 0.0
        for i in range(256):
            for j in range(2):
                self.lut_pow_4bit[i] += (float((i>>(4*j))&(0xf))-7.5)**2
        for i in range(256):
            for j in range(4):
                self.lut_pow_2bit[i] += (float((i>>(2*j))&(0x3))-1.5)**2

    def time_from_hdr(self,hdr):
        # Given databuf header, return start time of block
        try:
            packets_per_sec = (abs(hdr['OBSBW']) * 1e6 * 2.0 
                    / (hdr['PKTSIZE'] * 8 / hdr['NBITS']))
            smjd = float(hdr['STT_SMJD']) + hdr['PKTIDX']/packets_per_sec
            return float(hdr['STT_IMJD']) + smjd/86400.0
        except KeyError:
            return None

    def raw_data_to_power(self,raw):
        # Given raw data array return pol0 and pol1 powers averaging
        # the first nbyte_sum bytes in array.
        pol0_pow = (self.lut_pow[raw[0:2*self.nbytes_sum:2]]).mean()
        pol1_pow = (self.lut_pow[raw[1:2*self.nbytes_sum:2]]).mean()
        return (pol0_pow, pol1_pow)

    def update_values(self):
        # Read values from all databufs, add new ones to array
        gd = guppi_databuf()
        for ib in range(gd.n_block):
            try:
                gd.read_hdr(ib)
                # Read time, skip ones that already exist
                t = self.time_from_hdr(gd.hdr[ib])
                if (t is None) or (t in self.time): continue
                if gd.hdr[ib]['NBITS']==2:
                    self.lut_pow = self.lut_pow_2bit
                elif gd.hdr[ib]['NBITS']==4:
                    self.lut_pow = self.lut_pow_4bit
                else:
                    self.lut_pow = self.lut_pow_8bit
                (pow_p0,pow_p1) = self.raw_data_to_power(gd.data(ib).ravel())
                self.time.append(t)
                self.pow0.append(pow_p0)
                self.pow1.append(pow_p1)
            except KeyError:
                pass

    def prune_values(self):
        # Trim any results that are older than the limit
        if len(self.time)==0: return
        cut_time = max(self.time) - self.timespan/86400.0
        i = 0
        while i < len(self.time):
            if self.time[i] < cut_time:
                self.time.pop(i)
                self.pow0.pop(i)
                self.pow1.pop(i)
            else:
                i += 1


if __name__ == "__main__":
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.lines import Line2D
    import matplotlib.pyplot as plt
    import matplotlib.animation as anim
    import matplotlib.dates as mpldates
    import datetime as dt

    fig, ax = plt.subplots()
    line0 = Line2D([], [], color='b', lw=2.0)
    line1 = Line2D([], [], color='g', lw=2.0)
    ax.add_line(line0)
    ax.add_line(line1)
    ax.set_xlabel('Time')
    ax.set_ylabel('Power')
    ax.grid()

    def mjd2date(mjd):
        return mpldates.num2date(numpy.array(mjd) + 678576.0)

    def update_line(stuff):
        (t_mjd,p0,p1) = stuff
        t_dt = mjd2date(t_mjd)
        #tmax = max(t)
        #ax.set_xlim(tmax - 300.0/86400.0, tmax)
        tmax = max(t_dt)
        ax.set_xlim(tmax - dt.timedelta(seconds=300), tmax)
        ax.set_ylim(min(p0+p1), max(p0+p1))
        ax.figure.canvas.draw()
        line0.set_data(t_dt,p0)
        line1.set_data(t_dt,p1)
        return line0, line1

    def fake_data():
        t = [0.0]
        p0 = [0.0]
        p1 = [1.0]
        while True:
            t.append(t[-1]+1.0)
            p0.append(numpy.random.rand())
            p1.append(numpy.random.rand()+1.0)
            if len(t) > 50:
                t.pop(0)
                p0.pop(0)
                p1.pop(0)
            yield t, p0, p1

    def get_power():
        yp = yuppi_power_mon()
        while True:
            yp.update_values()
            yp.prune_values()
            yield yp.time, yp.pow0, yp.pow1

    ani = anim.FuncAnimation(fig, update_line, get_power,
            blit=True,interval=500,repeat=False,save_count=0)

    plt.show()

