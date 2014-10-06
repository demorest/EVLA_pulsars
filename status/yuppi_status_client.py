#! /usr/bin/env python

# connect to all nodes, print awesome screen

import time
import Pyro4
Pyro4.config.HMAC_KEY='blahblahblah'

# connect em
nodelist = ["cbe-node-%02d" % i for i in range(1,33)]
status = {}
for node in nodelist:
    uri = "PYRO:yuppi_status@%s:50100" % node
    status[node] = Pyro4.Proxy(uri)

def get(d,k):
    try:
        return d[k]
    except KeyError:
        return "unk"

import curses, curses.wrapper

def do_display(scr):
    scr.nodelay(1)
    run = True

    # The usual color scheme
    curses.init_pair(1,curses.COLOR_CYAN,curses.COLOR_BLACK)
    kc = curses.color_pair(1)
    curses.init_pair(2,curses.COLOR_GREEN,curses.COLOR_BLACK)
    vc = curses.color_pair(2)
    curses.init_pair(3,curses.COLOR_WHITE,curses.COLOR_RED)
    ec = curses.color_pair(3)

    while run:

        # set up
        scr.erase()
        scr.border()
        (ymax,xmax) = scr.getmaxyx()

        curline = 0
        col = 2
        scr.addstr(curline,col,"YUPPI node status:",kc)
        curline+=1

        rcol = 14
        statfmt = "%9s %8s %9s %9s %8s %6s"
        scr.addstr(curline,rcol,statfmt%("PULSE","DAQ","NET","DROP","BLK", "FREQ"),kc)

        # Loop over nodes
        for node in nodelist:

            curline += 1
            if curline > ymax-1:
                scr.addstr(ymax-1,col,"--Increase window size--",ec)
                continue

            scr.addstr(curline,col,node,kc)
            try:
                status[node].update()
                shmem = status[node].get_shmem_keys()
            except:
                scr.addstr(curline,rcol,"No status connection",ec)
                continue

            if shmem==None:
                scr.addstr(curline,rcol,"No shmem",vc)
                continue

            # Build status string
            try:
                dp = filter(bool,shmem['DAQPULSE'].split(' '))[3]
            except KeyError:
                dp = "unk"

            try:
                dt = "%.2e" % float(shmem['DROPTOT'])
            except:
                dt = "unk"

            ds = get(shmem,'DAQSTATE')
            ns = get(shmem,'NETSTAT')
            fr = get(shmem,'OBSFREQ')
            db = get(shmem,'DROPBLK')

            statstring = statfmt % (dp, ds, ns, dt, db, fr)

            # print it to screen
            scr.addstr(curline,rcol,statstring,vc)

        scr.refresh()
        time.sleep(1)
        c = scr.getch()
        while (c!=curses.ERR):
            if (c==ord('q')):
                run = False
            c = scr.getch()

try:
    curses.wrapper(do_display)
except KeyboardInterrupt:
    print "Exiting.."
