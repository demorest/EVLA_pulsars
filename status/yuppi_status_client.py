#! /usr/bin/env python

# connect to all nodes, print awesome screen

import time
import Pyro4
Pyro4.config.HMAC_KEY='blahblahblah'

# connect em
nodelist = ["cbe-node-%02d" % i for i in range(1,17)]
status = {}
for node in nodelist:
    uri = "PYRO:yuppi_status@%s:50100" % node
    status[node] = Pyro4.Proxy(uri)

def get(d,k):
    try:
        return d[k]
    except KeyError:
        return "unk"

# Also connect to remote supervisors
import xmlrpclib
import socket
supervisor = {}
down = {}
for node in nodelist:
    uri = "http://%s:9200" % node
    supervisor[node] = xmlrpclib.Server(uri)
    down[node] = False 

import curses, curses.wrapper

ndaq = 4

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

        scol = 14
        #supfmt = "%8s %8s %8s %8s"
        supfmt = "%4s %4s %4s %4s %4s %4s"
        supnchar = 3
        scr.addstr(curline,scol,supfmt % ("sup", "ctrl", "daq0", "daq1", "daq2", "daq3"),kc)

        statfmt = "%9s %4s %8s %5s %6s"
        statnchar = 4
        #rcol = [50, 100, 150, 200]
        rcol = [44+37*i for i in range(ndaq)]
        for i in range(ndaq):
            scr.addstr(curline,rcol[i],statfmt%("PULSE","DAQ","NET","DROP",
                "FREQ"),kc)

        # Loop over nodes
        for node in nodelist:

            curline += 1
            if curline > ymax-1:
                scr.addstr(ymax-1,col,"--Increase window size--",ec)
                continue

            scr.addstr(curline,col,node,kc)

            if down[node]:
                scr.addstr(curline,scol,"Node unreachable, ignoring",ec)
                continue

            # Check for supervisor connection
            try:
                sup_state = supervisor[node].supervisor.getState()['statename']
                #scr.addstr(curline,scol,sup_state,vc)
            except socket.error as e:
                if e.errno==113: # No route to host
                    down[node] = True
                scr.addstr(curline,scol,"No connection",ec)
                sup_state = "OFF"
                continue
            except:
                sup_state = "OFF"
                scr.addstr(curline,scol,"No connection",ec)
                continue

            if sup_state != "OFF":
                states = {}
                for proc in (("yuppi:yuppi_controller",) +  
                        tuple("yuppi:guppi_daq_%d"%i for i in range(ndaq))):
                        #"yuppi:guppi_daq_0", "yuppi:guppi_daq_1"):
                    try:
                        states[proc] = supervisor[node].supervisor.getProcessInfo(proc)['statename']
                    except:
                        states[proc] = 'err'

                scr.addstr(curline,scol,supfmt % ((sup_state[:supnchar], 
                    states['yuppi:yuppi_controller'][:supnchar],) 
                    + tuple(states['yuppi:guppi_daq_%d'%i][:supnchar] for i in range(ndaq))),
                    #states['yuppi:guppi_daq_0'][:supnchar],
                    #states['yuppi:guppi_daq_1'][:supnchar]), 
                    vc)

            # Check for yuppi_status connection
            try:
                status[node].update()
            except:
                scr.addstr(curline,rcol[0],"No status connection",ec)
                continue

            for i in range(ndaq):

                try:
                    shmem = status[node].get_shmem_keys(i)
                except:
                    shmem = None

                if shmem==None:
                    scr.addstr(curline,rcol[i],"No shmem",vc)
                    continue

                # Build status string
                try:
                    dp = filter(bool,shmem['DAQPULSE'].split(' '))[3]
                except KeyError:
                    dp = "unk"

                try:
                    dt = "%.0e" % float(shmem['DROPTOT'])
                except:
                    dt = "unk"

                ds = get(shmem,'DAQSTATE')
                ns = get(shmem,'NETSTAT')
                fr = get(shmem,'OBSFREQ')

                statstring = statfmt % (dp, ds[:statnchar], ns[:8], dt, fr)

                # print it to screen, red if droptot > 10%
                try:
                    cc = ec if float(dt)>0.1 else vc
                except ValueError:
                    cc = vc
                scr.addstr(curline,rcol[i],statstring,cc)

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
