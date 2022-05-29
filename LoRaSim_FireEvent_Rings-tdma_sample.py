"""
 LoRaSim: simulate collisions in LoRa
 Copyright © 2016 Thiemo Voigt <thiemo@sics.se> and Martin Bor <m.bor@lancaster.ac.uk>

 This work is licensed under the Creative Commons Attribution 4.0
 International License. To view a copy of this license,
 visit http://creativecommons.org/licenses/by/4.0/.

 Do LoRa Low-Power Wide-Area Networks Scale? Martin Bor, Utz Roedig, Thiemo Voigt
 and Juan Alonso, MSWiM '16, http://dx.doi.org/10.1145/2988287.2989163

 $Date: 2016-10-17 13:23:52 +0100 (Mon, 17 Oct 2016) $
 $Revision: 218 $
"""

"""
 SYNOPSIS:
   ./loraDir.py <nodes> <avgsend> <experiment> <simtime> <packet length> [collision]
 DESCRIPTION:
    nodes
        number of nodes to simulate
    avgsend
        average sending interval in milliseconds
    experiment
        experiment is an integer that determines with what radio settings the
        simulation is run. All nodes are configured with a fixed transmit power
        and a single transmit frequency, unless stated otherwise.
        0   use the settings with the the slowest datarate (SF12, BW125, CR4/8).
        1   similair to experiment 0, but use a random choice of 3 transmit
            frequencies.
        2   use the settings with the fastest data rate (SF6, BW500, CR4/5).
        3   optimise the setting per node based on the distance to the gateway.
        4   use the settings as defined in LoRaWAN (SF12, BW125, CR4/5).
        5   similair to experiment 3, but also optimises the transmit power.
    simtime
        total running time in milliseconds
    collision
        set to 1 to enable the full collision check, 0 to use a simplified check.
        With the simplified check, two messages collide when they arrive at the
        same time, on the same frequency and spreading factor. The full collision
        check considers the 'capture effect', whereby a collision of one or the
 OUTPUT
    The result of every simulation run will be appended to a file named expX.dat,
    whereby X is the experiment number. The file contains a space separated table
    of values for nodes, collisions, transmissions and total energy spent. The
    data file can be easily plotted using e.g. gnuplot.
"""

import simpy
import random
import math
import sys
import matplotlib.pyplot as plt
import numpy as np
import os
import csv
from progressbarsimple import ProgressBar
from progress.bar import Bar
import winsound
import pandas as pd
import jenkspy
from jenkspy import JenksNaturalBreaks

# progressbar flag
PROG_BAR = False

# experiments:
# 0: packet with longest airtime, aloha-style experiment
# 0: one with 3 frequencies, 1 with 1 frequency
# 2: with shortest packets, still aloha-style
# 3: with shortest possible packets depending on distance


# this is an array with measured values for sensitivity
# see paper, Table 3

sf7 = np.array([7, -126.5, -124.25, -120.75])
sf8 = np.array([8, -127.25, -126.75, -124.0])
sf9 = np.array([9, -131.25, -128.25, -127.5])
sf10 = np.array([10, -132.75, -130.25, -128.75])
sf11 = np.array([11, -134.5, -132.75, -128.75])
sf12 = np.array([12, -133.25, -132.25, -132.25])

Ptx = 14
gamma = 2.08
d0 = 1000.0
var = 0  # variance ignored for now
Lpld0 = 127.41
GL = 0
sensi = np.array([sf7, sf8, sf9, sf10, sf11, sf12])
minsensi = -132.5
bsId = 1

global myProgressBar
global t_e  # event start time
global pkts_sent, pkts_gen, timeg, times, prev_time, pkts_gen_prev, pkts_sent_prev
global ring

# event epicenter
evep_x = 3250
evep_y = 3250
d_th = 150  # cut-off distance
# W = 200  # width of window
W = 1000  # width of window

Up = 6.4  # event propagation speed
RING_WIDTH = 50
RING_COUNT = 60

# event driven traffic
EVENT_TRAFFIC = True
# EVENT_TRAFFIC = False
FIRE_RINGS_ch_sf = True
# FIRE_RINGS_ch_sf = False
# FIRE_RINGS_tdma_simple = True
FIRE_RINGS_tdma_simple = False
FIRE_RINGS_TDMA_multi = True
# FIRE_RINGS_TDMA_multi = False


T_MODEL = 'RAISEDCOS'
# T_MODEL = 'DECAYINGEXP'
a = 0.005

# nrNodes = 13741
nrNodes = 5700
# nrNodes = 2200
avgSendTime = None
experiment = 5
# simtime = 600000
simtime = 60000
payloadlen = 20

# do the full collision check
full_collision = True

# get arguments
print("Nodes:", nrNodes)
# print("AvgSendTime (exp. distributed):", avgSendTime)
# print("Experiment: ", experiment)
print("Simtime: ", simtime)
print("payload size: ", payloadlen)
print("Full Collision: ", full_collision)

print("\nEVENT_TRAFFIC", EVENT_TRAFFIC)
print("FIRE_RINGS_ch_sf", FIRE_RINGS_ch_sf)
print("FIRE_RINGS_tdma_simple", FIRE_RINGS_tdma_simple)
print("FIRE_RINGS_TDMA_multi", FIRE_RINGS_TDMA_multi, "\n")

if PROG_BAR:
    myProgressBar = ProgressBar(nElements=100, nIterations=simtime)

on_fire_ids = []
on_danger_ids = []
normal_ids = []
nodes_burst_trx_ids = []

pkts_sent = []
pkts_gen = []
time = []
timeg = []
times = []
prev_time = 0
pkts_gen_prev = 0
pkts_sent_prev = 0

centroid = []

if EVENT_TRAFFIC:
    # t_e = simtime / 2
    t_e = simtime / 20
    # print("Time of event:", t_e)

if experiment in [0, 1, 4]:
    minsensi = sensi[5, 2]  # 5th row is SF12, 2nd column is BW125
elif experiment == 2:
    minsensi = -112.0  # no experiments, so value from datasheet
elif experiment == 3:
    minsensi = np.amin(sensi)  # Experiment 3 can use any setting, so take minimum
# elif experiment == 5:
#     minsensi = np.amin(sensi)  # Experiment 5 can use any setting, so take minimum

Lpl = Ptx - minsensi
# print("amin", minsensi, "Lpl", Lpl)
maxDist = d0 * (math.e ** ((Lpl - Lpld0) / (10.0 * gamma)))
# print("maxDist:", maxDist)

# base station placement
bsx = maxDist + 10
bsy = maxDist + 10
xmax = bsx + maxDist + 20
ymax = bsy + maxDist + 20

nodes = []
packetsAtBS = []
env = simpy.Environment()

# maximum number of packets the BS can receive at the same time
maxBSReceives = 8

# max distance: 300m in city, 3000 m outside (5 km Utz experiment)
# also more unit-disc like according to Utz
nrCollisions = 0
nrReceived: int = 0
nrProcessed = 0
nrLost = 0

sumgenpkts = 0
sum_airt = [0]
prev_sum_airt = 0
busy = False

if not EVENT_TRAFFIC:
    Up = '-'


#
# check for collisions at base station
# Note: called before a packet (or rather node) is inserted into the list
#
# conditions for collions:
#     1. same sf
#     2. frequency, see function below (Martins email, not implementet yet):
def checkcollision(packet):
    col = 0  # flag needed since there might be several collisions for packet
    processing = 0
    global packetsAtBS
    for i in range(0, len(packetsAtBS)):
        if packetsAtBS[i].packet.processed == 1:
            processing = processing + 1
    if processing > maxBSReceives:
        # print("too long: {}".format(len(packetsAtBS)))
        packet.processed = 0
    else:
        packet.processed = 1

    if packetsAtBS:
        # print("CHECK node {} (sf:{} bw:{} freq:{:.6e}) others: {}".format(
        #     packet.nodeid, packet.sf, packet.bw, packet.freq,
        #     len(packetsAtBS)))
        for other in packetsAtBS:
            if other.nodeid != packet.nodeid:
                # print(">> node {} (sf:{} bw:{} freq:{:.6e})".format(
                #     other.nodeid, other.packet.sf, other.packet.bw, other.packet.freq))
                # simple collision
                if frequencyCollision(packet, other.packet) \
                        and sfCollision(packet, other.packet):
                    if full_collision:
                        if timingCollision(packet, other.packet):
                            # check who collides in the power domain
                            c = powerCollision(packet, other.packet)
                            # mark all the collided packets
                            # either this one, the other one, or both
                            for p in c:
                                p.collided = 1
                                if p == packet:
                                    col = 1
                        else:
                            # no timing collision, all fine
                            pass
                    else:
                        packet.collided = 1
                        other.packet.collided = 1  # other also got lost, if it wasn't lost already
                        col = 1
        return col
    return 0


#
# frequencyCollision, conditions
#
#        |f1-f2| <= 120 kHz if f1 or f2 has bw 500
#        |f1-f2| <= 60 kHz if f1 or f2 has bw 250
#        |f1-f2| <= 30 kHz if f1 or f2 has bw 125
def frequencyCollision(p1, p2):
    if abs(p1.freq - p2.freq) <= 120 and (p1.bw == 500 or p2.bw == 500):
        # print("frequency coll 500")
        return True
    elif abs(p1.freq - p2.freq) <= 60 and (p1.bw == 250 or p2.bw == 250):
        # print("frequency coll 250")
        return True
    else:
        if abs(p1.freq - p2.freq) <= 30:
            # print("frequency coll 125")
            return True
        # else:
    # print("no frequency coll")
    return False


#
# sfCollision, conditions
#
#       sf1 == sf2
#
def sfCollision(p1, p2):
    if p1.sf == p2.sf:
        print("collision sf node {} and node {}".format(p1.nodeid, p2.nodeid))
        # p2 may have been lost too, will be marked by other checks
        return True
    # print("no sf collision")
    return False


def powerCollision(p1, p2):
    powerThreshold = 6  # dB
    # print("pwr: node {0.nodeid} {0.rssi:3.2f} dBm node {1.nodeid} {1.rssi:3.2f} dBm; diff {2:3.2f} dBm".format(p1, p2,
    #                                                                                                            round(
    #                                                                                                                p1.rssi - p2.rssi,
    #                                                                                                                2)))
    if abs(p1.rssi - p2.rssi) < powerThreshold:
        # print("collision pwr both node {} and node {}".format(p1.nodeid, p2.nodeid))
        # packets are too close to each other, both collide
        # return both packets as casualties
        return (p1, p2)
    elif p1.rssi - p2.rssi < powerThreshold:
        # p2 overpowered p1, return p1 as casualty
        # print("collision pwr node {} overpowered node {}".format(p2.nodeid, p1.nodeid))
        return (p1,)
    # print("p1 wins, p2 lost")
    # p2 was the weaker packet, return it as a casualty
    return (p2,)


def timingCollision(p1, p2):
    # assuming p1 is the freshly arrived packet and this is the last check
    # we've already determined that p1 is a weak packet, so the only
    # way we can win is by being late enough (only the first n - 5 preamble symbols overlap)

    # assuming 8 preamble symbols
    Npream = 8

    # we can lose at most (Npream - 5) * Tsym of our preamble
    Tpreamb = 2 ** p1.sf / (1.0 * p1.bw) * (Npream - 5)

    # check whether p2 ends in p1's critical section
    p2_end = p2.addTime + p2.rectime
    p1_cs = env.now + Tpreamb
    # print("collision timing node {} ({},{},{}) node {} ({},{})".format(
    #     p1.nodeid, env.now - env.now, p1_cs - env.now, p1.rectime,
    #     p2.nodeid, p2.addTime - env.now, p2_end - env.now
    # ))
    if p1_cs < p2_end:
        # p1 collided with p2 and lost
        # print("not late enough")
        return True
    # print("saved by the preamble")
    return False


# this function computes the airtime of a packet
# according to LoraDesignGuide_STD.pdf
#
def airtime(sf, cr, pl, bw):
    H = 0  # implicit header disabled (H=0) or not (H=1)
    DE = 0  # low data rate optimization enabled (=1) or not (=0)
    Npream = 8  # number of preamble symbol (12.25  from Utz paper)

    if bw == 125 and sf in [11, 12]:
        # low data rate optimization mandated for BW125 with SF11 and SF12
        DE = 1
    if sf == 6:
        # can only have implicit header with SF6
        H = 1

    Tsym = (2.0 ** sf) / bw
    Tpream = (Npream + 4.25) * Tsym
    # print("sf", sf, " cr", cr, "pl", pl, "bw", bw)
    payloadSymbNB = 8 + max(math.ceil((8.0 * pl - 4.0 * sf + 28 + 16 - 20 * H) / (4.0 * (sf - 2 * DE))) * (cr + 4), 0)
    Tpayload = payloadSymbNB * Tsym

    # print("Airtime:",Tpream + Tpayload)

    return Tpream + Tpayload


# pulse function δ that defines the event (burst traffic) duration
# return 1 if the event is happening and 0 if not
def d(z):
    if z >= 0:
        return 1
    else:
        return 0


#
# this function creates a node
#
class LoraNode:
    def __init__(self, nodeid, bs, period, packetlen):
        self.nodeid = nodeid
        self.period = period
        self.bs = bs
        self.x = 0
        self.y = 0
        self.ring = -1
        if FIRE_RINGS_tdma_simple:
            self.ts_trx = 0

        # this is very complex procedure for placing nodes
        # and ensure minimum distance between each pair of nodes
        found = 0
        rounds = 0
        global nodes
        while found == 0 and rounds < 100:
            a = random.random()
            b = random.random()
            if b < a:
                a, b = b, a
            posx = b * maxDist * math.cos(2 * math.pi * a / b) + bsx
            posy = b * maxDist * math.sin(2 * math.pi * a / b) + bsy
            if len(nodes) > 0:
                for index, n in enumerate(nodes):
                    dist = np.sqrt(((abs(n.x - posx)) ** 2) + ((abs(n.y - posy)) ** 2))
                    # if dist >= 10:
                    if dist >= 20:
                        found = 1
                        self.x = posx
                        self.y = posy
                    else:
                        rounds = rounds + 1
                        if rounds == 100:
                            print("could not place new node, giving up")
                            exit(-1)
            else:
                # print("first node")
                self.x = posx
                self.y = posy
                found = 1

        # distance from the Gateway (base station)
        self.dist = np.sqrt((self.x - bsx) * (self.x - bsx) + (self.y - bsy) * (self.y - bsy))
        # print('node %d' % nodeid, "x", self.x, "y", self.y, "dist: ", self.dist)

        self.packet = LoraPacket(self.nodeid, packetlen, self.dist)
        self.sent = 0

        # distance from the event epicenter
        self.dist_epicenter = np.sqrt((self.x - evep_x) * (self.x - evep_x) + (self.y - evep_y) * (self.y - evep_y))

        # parameters for event generated traffic
        if T_MODEL == 'RAISEDCOS':
            self.delta_n = None  # spatial correlation factor
            if self.dist_epicenter < d_th:
                self.delta_n = 1
                on_fire_ids.append(self.nodeid)
            elif d_th <= self.dist_epicenter < (2 * W - d_th):
                self.delta_n = 1 / 2 * (1 - np.sin((np.pi * (self.dist_epicenter - W)) / (2 * (W - d_th))))
                on_danger_ids.append(self.nodeid)
            elif self.dist_epicenter >= 2 * W - d_th:
                self.delta_n = 0
                normal_ids.append(self.nodeid)
        elif T_MODEL == 'DECAYINGEXP':
            self.delta_n = np.exp(-a * self.dist_epicenter)
            if self.dist_epicenter < d_th:
                on_fire_ids.append(self.nodeid)
            elif d_th < self.dist_epicenter < 2 * W - d_th:
                on_danger_ids.append(self.nodeid)
            elif self.dist_epicenter >= 2 * W - d_th:
                normal_ids.append(self.nodeid)

        if PROG_BAR:
            myProgressBar.progress(len(nodes))

    def get_rate(self):
        lamda = random.choices(population=[6, 2, 1, 0.5], weights=[0.05, 0.25, 0.4, 0.3])
        return lamda[0] / 3600000

    def theta_helper(self, t):
        return d(t - t_e - (self.dist_epicenter / Up) * 1000)

    def theta(self, t):
        return self.theta_helper(t) * self.delta_n


#
# this function creates a packet (associated with a node)
# it also sets all parameters, currently random
#
class LoraPacket:
    def __init__(self, nodeid, plen, distance):
        global experiment
        global Ptx
        global gamma
        global d0
        global var
        global Lpld0
        global GL
        global ring

        self.nodeid = nodeid
        self.txpow = Ptx

        self.airt = 0

        # randomize configuration values
        # self.sf = random.choice([12,11,11,10,10,10,10,9,9,9,9,9,9,9,9,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8])
        # self.sf = random.choice([8,9,10,11,12])
        # self.sf = random.choice([8,8,8,9,9,9,10,10,11,12])
        # self.sf = random.choice([12,11,11,10,10,10,9,9,9,9,8,8,8,8,8])
        # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,9,9,9,10,10,10,10,10,11,11,11,12])
        # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,10,10,10,10,11,11,12])
        self.cr = random.randint(1, 4)
        # self.bw = random.choice([125, 250, 500])

        # for certain experiments override these
        if experiment == 1 or experiment == 0:
            self.sf = 12
            self.cr = 4
            self.bw = 125

        # for certain experiments override these
        if experiment == 2:
            self.sf = 6
            self.cr = 1
            self.bw = 500
        # lorawan
        if experiment == 4:
            self.sf = 12
            self.cr = 1
            self.bw = 125

        # for experiment 3 find the best setting
        # OBS, some hardcoded values
        Prx = self.txpow  ## zero path loss by default

        # log-shadow
        Lpl = Lpld0 + 10 * gamma * math.log(distance / d0)

        # print("Lpl:", Lpl)

        # Prx = self.txpow - GL - Lpl

        if (experiment == 3) or (experiment == 5):
            minairtime = 9999
            minsf = 0
            minbw = 0

            # print("Prx:", Prx)
            self.cr = 1
            self.bw = 125

            # if not FIRE_RINGS_ch_sf and not FIRE_RINGS_tdma_simple:
            #     self.sf = random.choice([7, 8, 9, 10, 11, 12])
            # else:
            #     self.sf = random.choice([7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 11, 12])

            # self.sf = random.choice([7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 11, 12])

            self.sf = random.choice([7, 8, 9, 10, 11, 12])
            # self.sf = 7
            # self.sf = random.choice([12,11,11,10,10,10,10,9,9,9,9,9,9,9,9,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8])
            # self.sf = random.choice([8,9,10,11,12])
            # self.sf = random.choice([8,8,8,9,9,9,10,10,11,12])
            # self.sf = random.choice([12,11,11,10,10,10,9,9,9,9,8,8,8,8,8])
            # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,9,9,9,10,10,10,10,10,11,11,11,12])
            # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,10,10,10,10,11,11,12])

            at = airtime(self.sf, self.cr, plen, self.bw)

            self.airt = at

            if at < minairtime:
                minairtime = at
                minsf = self.sf
                minbw = self.bw
                minsensi = -88
            if minairtime == 9999:
                # print("does not reach base station")
                exit(-1)
            # print("best sf:", minsf, " best bw: ", minbw, "best airtime:", minairtime)
            self.rectime = minairtime
            self.bw = minbw
            self.cr = 1

            Ch = 0
            h_b = 20
            Lu = 69.55 + 26.16 * math.log10(self.bw) - 13.82 * math.log10(h_b) - Ch + (
                    44.9 - 6.55 * math.log10(h_b)) * math.log10(distance)
            L0 = Lu - 4.78 * (math.log10(self.bw)) ** 2 + 18.33 * math.log10(self.bw) - 40.94
            # print("L0:", L0)

            # Prx = self.txpow - GL - L0
            Prx = self.txpow - GL - Lpl

            if experiment == 5:
                # reduce the txpower if there's room left
                self.txpow = max(2, self.txpow - math.floor(Prx - minsensi))
                Prx = self.txpow - GL - Lpl
                # Prx = self.txpow - GL - L0
                # print('minsesi {} best txpow {}'.format(minsensi, self.txpow))

        # transmission range, needs update XXX
        self.transRange = 150
        self.pl = plen
        self.symTime = (2.0 ** self.sf) / self.bw
        self.arriveTime = 0
        self.sentTime = 0
        self.rssi = Prx
        # frequencies: lower bound + number of 61 Hz steps
        # self.freq = 860000000 + random.randint(0,2622950)

        # for certain experiments override these and
        # choose some random frequences

        # self.freq = random.choice([866500000,866700000,866900000,867100000,867300000,867500000,867700000,867900000,868100000, 868300000, 868500000,868700000,868900000,869100000,869300000,869500000])

        # self.freq = random.choice([868100000, 868300000, 868500000, 868700000, 868900000, 869100000, 869300000, 869500000])
        self.freq = random.choice(
            [868100000, 868300000, 868500000, 867100000, 867300000, 867500000, 867700000, 867900000])

        # print("frequency", self.freq, "symTime ", self.symTime)
        # print("bw", self.bw, "sf", self.sf, "cr", self.cr, "rssi", self.rssi)
        self.rectime = airtime(self.sf, self.cr, self.pl, self.bw)
        # print("rectime node ", self.nodeid, "  ", self.rectime)
        # denote if packet is collided
        self.collided = 0
        self.processed = 0


#
# main discrete event loop, runs for each node
# a global list of packet being processed at the gateway
# is maintained
#


def transmit(env, node):
    while True:
        # inter-arrival time
        wtime = random.expovariate(node.get_rate())
        yield env.timeout(wtime)

        # packet arrives -> add to base station
        node.sent = node.sent + 1

        if node in packetsAtBS:
            print("ERROR: packet already in")
        else:
            sensitivity = sensi[node.packet.sf - 7, [125, 250, 500].index(node.packet.bw) + 1]
            if node.packet.rssi < sensitivity:
                print("node {}: packet will be lost".format(node.nodeid))
                node.packet.lost = True
            else:
                node.packet.lost = False
                # adding packet if no collision
                if checkcollision(node.packet) == 1:
                    node.packet.collided = 1
                else:
                    node.packet.collided = 0
                packetsAtBS.append(node)
                node.packet.addTime = env.now

        # time sending and receiving
        yield env.timeout(node.packet.rectime)

        if node.packet.lost:
            global nrLost
            nrLost += 1
        if node.packet.collided == 1:
            global nrCollisions
            nrCollisions = nrCollisions + 1
        if node.packet.collided == 0 and not node.packet.lost:
            global nrReceived
            nrReceived = nrReceived + 1
        if node.packet.processed == 1:
            global nrProcessed
            nrProcessed = nrProcessed + 1

        # complete packet has been received by base station
        # can remove it
        if node in packetsAtBS:
            packetsAtBS.remove(node)
            # reset the packet
        node.packet.collided = 0
        node.packet.processed = 0
        node.packet.lost = False

        global prev_time, pkts_sent, pkts_gen, pkts_sent_prev, pkts_gen_prev
        sumsent = sum(s.sent for s in nodes)

        if env.now - prev_time >= 500:
            pkts_gen.append(sumsent - pkts_gen_prev)
            pkts_sent.append(nrReceived - pkts_sent_prev)
            time.append(env.now / 1000)
            prev_time = env.now
            pkts_gen_prev = sumsent
            pkts_sent_prev = nrReceived

            if PROG_BAR:
                myProgressBar.progress(int(env.now))


def transmit_event(env, node):
    global prev_time, pkts_sent, pkts_gen, pkts_sent_prev, pkts_gen_prev, sumsent, nodes_burst_trx_ids, sumgenpkts, sum_airt, prev_sum_airt
    global nrReceived, nrLost, nrCollisions, nrProcessed, busy
    global centroid

    p = random.uniform(0, 1)
    while True:
        wtime = random.expovariate(node.get_rate())
        # p = random.uniform(0, 1)
        if p < node.theta(env.now) and (node.nodeid not in nodes_burst_trx_ids) and env.now >= t_e:
            print("====Burst traffic!====, from node", node.nodeid, "at:", env.now)
            nodes_burst_trx_ids.append(node.nodeid)
            wtime = 0

            # time sending and receiving
            # packet arrives -> add to base station
            # send(node)
            sumsent = sum(s.sent for s in nodes)
            if env.now - prev_time >= 500 and not busy:
                busy = True
                pkts_gen.append(sumsent - pkts_gen_prev)
                # pkts_gen.append(sumgenpkts - pkts_gen_prev)
                pkts_sent.append(nrReceived - pkts_sent_prev)
                time.append(env.now / 1000)
                timeg.append(env.now / 1000)
                times.append((env.now - max(sum_airt)) / 1000)
                prev_time = env.now
                pkts_gen_prev = sumsent
                # pkts_gen_prev = sumgenpkts
                pkts_sent_prev = nrReceived

                # print("time_sent:", env.now - max(sum_airt))
                # print("lag:", max(sum_airt))
                # print("avg. lag:", sum(sum_airt) / len(sum_airt))
                # print(env.now)
                sum_airt = [0]
                if PROG_BAR:
                    myProgressBar.progress(int(env.now))
                busy = False
        # else:
        if node.nodeid not in nodes_burst_trx_ids and (node.nodeid in on_fire_ids or node.nodeid in on_danger_ids):
            if wtime + env.now >= t_e:
                if env.now >= t_e:

                    # yield env.timeout(400)
                    yield env.timeout(10)

                    yield env.timeout(random.uniform(0, 1))

                    # print("[debug] continue for node", node.nodeid, "till event at:", env.now)
                    continue
                    wtime = 0
                else:
                    wtime = t_e - env.now

                    yield env.timeout(wtime)

                    yield env.timeout(random.uniform(0, 1))

                    continue
                    wtime = 0
            else:
                # break
                yield env.timeout(wtime)
                continue
                wtime = 0
            # yield env.timeout(wtime+10000)

        yield env.timeout(wtime)

        node.packet.arriveTime = env.now

        # SIMPLE TDMA SCHEDULING
        if FIRE_RINGS_tdma_simple:
            print("\nnodeid", node.nodeid)
            if node.ts_trx * TIMESLOT > env.now:
                print("env.now:", env.now, "wait for scheduled timeslot:")
                yield wait_trx_ts(env, node.ts_trx)
            else:
                # break
                pass

        # MULTI TDMA SCHEDULING
        if FIRE_RINGS_TDMA_multi:
            yield wait_trx_ts_MULTI(env, node.nodeid)
        # time sending and receiving
        # packet arrives -> add to base station

        node.sent = node.sent + 1

        sumgenpkts = sumgenpkts + 1

        print("starting transmission at:", env.now)

        if node in packetsAtBS:
            print("ERROR: packet already in")
        else:
            sensitivity = sensi[node.packet.sf - 7, [125, 250, 500].index(node.packet.bw) + 1]
            if node.packet.rssi < sensitivity:
                print("node {}: packet will be lost".format(node.nodeid))
                node.packet.lost = True
            else:
                node.packet.lost = False
                # adding packet if no collision
                if checkcollision(node.packet) == 1:
                    node.packet.collided = 1
                else:
                    node.packet.collided = 0
                packetsAtBS.append(node)
                node.packet.addTime = env.now

        print("transmitting at:", env.now)

        node.packet.sentTime = env.now

        yield env.timeout(node.packet.rectime)

        if node.packet.lost:
            # global nrLost
            nrLost = nrLost + 1
        if node.packet.collided == 1:
            # global nrCollisions
            nrCollisions = nrCollisions + 1

            # for DEBUG purposes
            # for i in range(50):
            #     if node.nodeid in ring[i]:
            #         print("-*-*- node ", node.nodeid, "in ring group:", i, " with packet sf:", node.packet.sf)
            #         print("--**-- Collision in ring group:", i)

        if node.packet.collided == 0 and not node.packet.lost:
            # global nrReceived
            nrReceived = nrReceived + 1

            # print(env.now-node.packet.addTime,"=",node.packet.airt)

        if node.packet.processed == 1:
            # global nrProcessed
            nrProcessed = nrProcessed + 1
            sum_airt.append(node.packet.airt)

        # complete packet has been received by base station
        # can remove it
        if node in packetsAtBS:
            packetsAtBS.remove(node)
            # reset the packet
        node.packet.collided = 0
        node.packet.processed = 0
        node.packet.lost = False
        # save stats for graphs
        sumsent = sum(s.sent for s in nodes)
        if env.now - prev_time >= 500 and not busy:
            busy = True
            pkts_gen.append(sumsent - pkts_gen_prev)
            # pkts_gen.append(sumgenpkts - pkts_gen_prev)
            pkts_sent.append(nrReceived - pkts_sent_prev)
            time.append(env.now / 1000)
            timeg.append(env.now / 1000)
            times.append((env.now - max(sum_airt)) / 1000)
            prev_time = env.now
            pkts_gen_prev = sumsent
            # pkts_gen_prev = sumgenpkts
            pkts_sent_prev = nrReceived

            # print("time_sent:", env.now - max(sum_airt))
            # print("lag:", max(sum_airt))
            # print("avg. lag:", sum(sum_airt) / len(sum_airt))
            # print(env.now)
            sum_airt = [0]
            if PROG_BAR:
                myProgressBar.progress(int(env.now))
            busy = False

        # yield env.timeout(100)


TIMESLOT = 2000


def wait_trx_ts(env: simpy.Environment, t: int):
    # w_nexttimeslot = TIMESLOT - (env.now - ((env.now // TIMESLOT) * TIMESLOT)) + t * TIMESLOT
    w_sch_ts = t * TIMESLOT - env.now + t_e

    print(w_sch_ts)
    print("-=-")
    return env.timeout(w_sch_ts)


def wait_trx_ts_MULTI(env: simpy.Environment, nid: int):
    # in what ring the node belongs to
    if nodes[nid].ring != -1:
        n_ring = nodes[nid].ring

        # wait for the previous ring to finish transmissions
        w_prev_ring_multi = prev_ring_w[nodes[nid].ring]

        # scheduling of node inside with specific channel in ring
        order = df[n_ring].loc[df[n_ring]['nodeid'] == nid]['order'].item()

        # timeslot duration of node inside with specific channel in ring
        timeslot = df[n_ring].loc[df[n_ring]['nodeid'] == nid]['timeslot'].item()

        if env.now > w_prev_ring_multi:
            w_time_tdma_multi = order * timeslot
        else:
            w_time_tdma_multi = order * timeslot + w_prev_ring_multi
        print("-waiting for...", w_time_tdma_multi)
        return env.timeout(w_time_tdma_multi)
    else:
        print("-----=NO RING GROUP=-----")
        return env.timeout(simtime)


# random.seed(0)
for i in range(0, nrNodes):
    # myNode takes period (in ms), base station id packetlen (in Bytes)
    # 1000000 = 16 min
    node = LoraNode(i, bsId, avgSendTime, payloadlen)

    nodes.append(node)

if FIRE_RINGS_ch_sf or FIRE_RINGS_tdma_simple or FIRE_RINGS_TDMA_multi:
    step = 0
    ring = [[] for _ in range(RING_COUNT)]
    for i in range(RING_COUNT):

        # create ring group
        for n in nodes:
            if step <= n.dist_epicenter < step + RING_WIDTH:
                ring[i].append(n.nodeid)
        step = step + RING_WIDTH
        temp_ring_node_obj = []

        # sort nodes in ring group according to their distance from the event epicenter
        for n in nodes:
            if n.nodeid in ring[i]:
                temp_ring_node_obj.append(n)
        temp_ring_node_obj.sort(key=lambda x: x.dist_epicenter)
        ring[i] = []
        for t in temp_ring_node_obj:
            # print(t.dist_epicenter)
            ring[i].append(t.nodeid)
        # print("---------")

        for j in ring[i]:
            nodes[j].ring = i

    if FIRE_RINGS_tdma_simple:
        ts_sch = (t_e / 1000) / 2
        # n_counter = 0
        for i in range(len(ring)):
            for j in range(len(ring[i])):
                # n_counter = n_counter + 1
                ts_sch = ts_sch + 1
                nodes[ring[i][j]].ts_trx = ts_sch
                # print(ts_sch)

    if FIRE_RINGS_ch_sf:
        # channel_list = [868100000, 868300000, 868500000, 867100000, 867300000, 867500000, 867700000, 867900000]
        # c = 0
        # for i in range(len(ring)):
        #     for j in range(len(ring[i])):
        #         if c == len(channel_list):
        #             c = 0
        #         nodes[ring[i][j]].packet.freq = channel_list[c]
        #         c = c + 1

        # assign both channels & sf in round-robin fashion
        c1 = 0
        c2 = 0
        sf_list = [7, 8, 9, 10, 11, 12]
        channel_list = [868100000, 868300000, 868500000, 867100000, 867300000, 867500000, 867700000, 867900000]
        for i in range(len(ring)):
            for j in range(len(ring[i])):
                if c1 == len(sf_list):
                    c1 = 0
                    c2 = c2 + 1
                if c2 == len(channel_list):
                    c2 = 0
                nodes[ring[i][j]].packet.sf = sf_list[c1]
                nodes[ring[i][j]].packet.freq = channel_list[c2]
                c1 = c1 + 1
            c1 = 0
            c2 = 0

    # multi synchronized tdma with variable timeslot duration per ring
    channel_list = [868100000, 868300000, 868500000, 867100000, 867300000, 867500000, 867700000, 867900000]
    if FIRE_RINGS_TDMA_multi:
        breaks = [[] for _ in range(RING_COUNT)]
        df = []

        for i in range(len(ring)):
            df_tmp = pd.DataFrame(columns=['nodeid', 'toa', 'ring'], dtype=object)
            for j in range(len(ring[i])):
                df_tmp = df_tmp.append(pd.Series([ring[i][j], nodes[ring[i][j]].packet.rectime + random.random(), i],
                                                 index=df_tmp.columns), ignore_index=True)

            df_tmp = df_tmp.astype({"nodeid": int, "toa": float, "ring": int})

            df.append(df_tmp)

            del df_tmp

            # if len(ring[i]) >= 9:
            #     breaks[i].extend(jenkspy.jenks_breaks(df[i]['toa'], nb_class=8))
            # else:
            #     breaks[i].extend(jenkspy.jenks_breaks(df[i]['toa'], nb_class=len(ring[i])-1))
            no_breaks = False
            if len(ring[i]) >= 9:
                breaks[i].extend(jenkspy.jenks_breaks(df[i]['toa'], nb_class=8))
            elif len(ring[i]) > 3:
                breaks[i].extend(jenkspy.jenks_breaks(df[i]['toa'], nb_class=len(ring[i]) - 1))
            else:
                no_breaks = True
                # breaks[i].extend(jenkspy.jenks_breaks(df[i]['toa'], nb_class=2))

            # fix identical breaks bug
            if not no_breaks:
                for b in range(len(breaks[i])):
                    breaks[i][b] = breaks[i][b] + random.random() * 0.001

                breaks[i].sort()
                breaks[i].pop(0)
                breaks[i].insert(0, 0)

                # apply clustering to channel-groups according to Jenks-Fischer algorithm
                if len(ring[i]) <= 8:
                    df[i]['channel'] = pd.cut(df[i]['toa'], bins=breaks[i],
                                              labels=[_ for _ in range(len(ring[i]) - 1)], include_lowest=True)
                else:
                    df[i]['channel'] = pd.cut(df[i]['toa'], bins=breaks[i],
                                              labels=[_ for _ in range(8)], include_lowest=True)
            else:
                df[i]['channel'] = np.random.randint(0, 7)

        prev_ring_w = [_ for _ in range(len(ring))]
        for i in range(len(ring)):
            for j in range(df[i]['channel'].max() + 1):
                df[i].loc[df[i]['channel'] == j, 'order'] = [_ for _ in
                                                             range(df[i].loc[df[i]['channel'] == j].__len__())]

                df[i].loc[df[i]['channel'] == j, 'timeslot'] = df[i].loc[df[i]['channel'] == j]['toa'].max() + 10

                df[i].loc[df[i]['channel'] == j, 'ch_tdma_dur'] = (df[i].loc[df[i]['channel'] == j][
                                                                       'order'].max() + 1) * (
                                                                          df[i].loc[df[i]['channel'] == j][
                                                                              'toa'].max() + 10)
            if i != 0:
                prev_ring_w[i] = df[i - 1]['ch_tdma_dur'].max() + prev_ring_w[i - 1] + random.randint(0,
                                                                                                      500)  # + 100 + random.randint(0, 500)
            else:
                prev_ring_w[i] = 0

        # assign channels to nodes
        for n in nodes:
            if n.ring != -1:
                n.packet.freq = channel_list[df[n.ring].loc[df[n.ring]['nodeid'] == n.nodeid, 'channel'].item()]

for n in nodes:
    if EVENT_TRAFFIC:
        env.process(transmit_event(env, n))
    else:
        env.process(transmit(env, n))

# prepare show

# start simulation
env.run(until=simtime)

nodes_burst_trx_ids = set(nodes_burst_trx_ids)
# pkts_sent.append(pkts_sent.pop(0))
# times, pkts_sent = zip(*sorted(zip(times, pkts_sent)))

# print(stats and save into file
print("nrCollisions ", nrCollisions)

# compute energy
# Transmit consumption in mA from -2 to +17 dBm
TX = [22, 22, 22, 23,  # RFO/PA0: -2..1
      24, 24, 24, 25, 25, 25, 25, 26, 31, 32, 34, 35, 44,  # PA_BOOST/PA1: 2..14
      82, 85, 90,  # PA_BOOST/PA1: 15..17
      105, 115, 125]  # PA_BOOST/PA1+PA2: 18..20
mA = 90  # current draw for TX = 17 dBm
V = 3.0  # voltage XXX
sent = sum(n.sent for n in nodes)

# for node in nodes:
#     energy = sum(node.packet.rectime * TX[int(node.packet.txpow) + 2] * V * node.sent for node in nodes) / 1e6
#
energy = 0
print("energy (in J): ", energy)
print("sent packets: ", sent)
print("collisions: ", nrCollisions)
print("received packets: ", nrReceived)
print("processed packets: ", nrProcessed)
print("lost packets: ", nrLost)


# data extraction rate
der = (sent - nrCollisions) / float(sent)
print("DER:", der)
der2 = nrReceived / float(sent)
print("DER method 2:", der2)
thr = nrReceived / (simtime / 1000)
print("Throughput: ", thr)

# pdr = nrReceived / float(sent)
pdr = max(pkts_sent) / max(pkts_gen)
# pdr = nrProcessed / float(sent)
# print("Packet Delivery Rate (PDR):", pdr)
print("Packet Delivery Rate (PDR):", pdr)

# save experiment data into a dat file that can be read by e.g. gnuplot
# name of file would be:  exp0.dat for experiment 0
fname = "exp" + str(experiment) + ".dat"
print(fname)
if os.path.isfile(fname):
    res = "\n" + str(nrNodes) + " " + str(nrCollisions) + " " + str(sent) + " " + str(energy) + " " + str(
        Up) + " " + str(pdr) + " " + str(der2) + " " + str(FIRE_RINGS_ch_sf)
else:
    res = "#nrNodes nrCollisions nrTransmissions OverallEnergy Up PDR DER2 FireRings\n" + str(nrNodes) + " " + str(
        nrCollisions) + " " + str(sent) + " " + str(energy) + " " + str(Up) + " " + str(pdr) + " " + str(
        der2) + " " + str(FIRE_RINGS_ch_sf)
with open(fname, "a") as myfile:
    myfile.write(res)
myfile.close()

fname_csv = "exp" + str(experiment) + ".csv"
print(fname_csv)
create_csv = True
if os.path.isfile(fname_csv):
    create_csv = False
else:
    create_csv = True
with open(fname_csv, mode='a+', newline='') as csv_file:
    fieldnames = ['#nrNodes', 'nrCollisions', 'nrTransmissions', 'OverallEnergy', 'Up', 'PDR', 'DER2', 'FireRings']
    if create_csv:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(fieldnames)
    else:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(
        [str(nrNodes), str(nrCollisions), str(sent), str(energy), str(Up), str(pdr), str(der2), str(FIRE_RINGS_ch_sf)])
csv_file.close()

fname_csv_gen_sen = "generated_delivered_v=" + str(Up) + "ms_n=" + str(nrNodes) + ".csv"
print(fname_csv_gen_sen)
create_csv_gen_sen = True
if os.path.isfile(fname_csv_gen_sen):
    create_csv_gen_sen = False
else:
    create_csv_gen_sen = True
with open(fname_csv_gen_sen, mode='a+', newline='') as csv_file:
    # fieldnames = ['timeg' + str(Up), '#pkts_gen' + str(Up), 'times' + str(Up), '#pkts_sent' + str(Up)]
    fieldnames = ['time' + str(Up), '#pkts_gen' + str(Up), '#pkts_sent' + str(Up)]
    if create_csv_gen_sen:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(fieldnames)
    else:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    for i in range(len(timeg)):
        # writer.writerow([timeg[i], pkts_gen[i], times[i], pkts_sent[i]])
        writer.writerow([time[i], pkts_gen[i], pkts_sent[i]])
csv_file.close()

# with open('nodes.txt','w') as nfile:
#     for n in nodes:
#         nfile.write("{} {} {}\n".format(n.x, n.y, n.nodeid))
# with open('basestation.txt', 'w') as bfile:
#     bfile.write("{} {} {}\n".format(bsx, bsy, 0))


winsound.Beep(540, 1000)
