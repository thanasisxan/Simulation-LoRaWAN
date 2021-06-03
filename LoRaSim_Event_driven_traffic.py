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

# do the full collision check
full_collision = True

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
    if (processing > maxBSReceives):
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
        # print("collision sf node {} and node {}".format(p1.nodeid, p2.nodeid))
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
    return Tpream + Tpayload


# pulse function δ that defines the event (burst traffic) duration
# return 1 if the event is happening and 0 if not
def d(z):
    if 0 <= z <= BURST_DURATION:
        # if 0 <= z:
        return 1
    else:
        return 0


#
# this function creates a node
#
class myNode():
    def __init__(self, nodeid, bs, period, packetlen):
        self.nodeid = nodeid
        self.period = period
        self.bs = bs
        self.x = 0
        self.y = 0

        # this is very complex prodecure for placing nodes
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
                    if dist >= 10:
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

        self.packet = myPacket(self.nodeid, packetlen, self.dist)
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
        return d(t - t_e - (self.dist_epicenter / Up) )

    def theta(self, t):
        return self.theta_helper(t) * self.delta_n


#
# this function creates a packet (associated with a node)
# it also sets all parameters, currently random
#
class myPacket():
    def __init__(self, nodeid, plen, distance):
        global experiment
        global Ptx
        global gamma
        global d0
        global var
        global Lpld0
        global GL

        self.nodeid = nodeid
        self.txpow = Ptx

        # randomize configuration values
        # self.sf = random.choice([12,11,11,10,10,10,10,9,9,9,9,9,9,9,9,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8])
        # self.sf = random.choice([8,9,10,11,12])
        # self.sf = random.choice([8,8,8,9,9,9,10,10,11,12])
        # self.sf = random.choice([12,11,11,10,10,10,9,9,9,9,8,8,8,8,8])
        # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,9,9,9,10,10,10,10,10,11,11,11,12])
        #        self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,10,10,10,10,11,11,12])
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
            self.sf = random.choice([7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 11, 12])
            # self.sf = random.choice([12,11,11,10,10,10,10,9,9,9,9,9,9,9,9,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8])
            # self.sf = random.choice([8,9,10,11,12])
            # self.sf = random.choice([8,8,8,9,9,9,10,10,11,12])
            # self.sf = random.choice([12,11,11,10,10,10,9,9,9,9,8,8,8,8,8])
            # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,9,9,9,10,10,10,10,10,11,11,11,12])
            # self.sf  = random.choice([8,8,8,8,8,8,8,8,8,8,8,8,9,9,9,9,9,9,10,10,10,10,11,11,12])

            at = airtime(self.sf, self.cr, plen, self.bw)
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

            Prx = self.txpow - GL - L0

            if experiment == 5:
                # reduce the txpower if there's room left
                self.txpow = max(2, self.txpow - math.floor(Prx - minsensi))
                # Prx = self.txpow - GL - Lpl
                Prx = self.txpow - GL - L0
                # print('minsesi {} best txpow {}'.format(minsensi, self.txpow))

        # transmission range, needs update XXX
        self.transRange = 150
        self.pl = plen
        self.symTime = (2.0 ** self.sf) / self.bw
        self.arriveTime = 0
        self.rssi = Prx
        # frequencies: lower bound + number of 61 Hz steps
        # self.freq = 860000000 + random.randint(0,2622950)

        # for certain experiments override these and
        # choose some random frequences

        self.freq = random.choice(
            [868100000, 868300000, 868500000, 868700000, 868900000, 869100000, 869300000, 869500000])
        # self.freq = random.choice([866500000,866700000,866900000,867100000,867300000,867500000,867700000,867900000,868100000, 868300000, 868500000,868700000,868900000,869100000,869300000,869500000])

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

        if env.now - prev_time >= 100:
            pkts_gen.append(sumsent - pkts_gen_prev)
            pkts_sent.append(nrReceived - pkts_sent_prev)
            time.append(env.now / 1000)
            prev_time = env.now
            pkts_gen_prev = sumsent
            pkts_sent_prev = nrReceived

            if PROG_BAR:
                myProgressBar.progress(int(env.now))


# transmit event
def transmit_event(env, node):
    # global nrReceived, nrLost, nrCollisions, nrProcessed
    global prev_time, pkts_sent, pkts_gen, pkts_sent_prev, pkts_gen_prev, sumsent
    global nrReceived, nrLost, nrCollisions, nrProcessed

    while True:
        p = random.uniform(0, 1)

        # if p < node.theta(env.now) and node.nodeid not in nodes_burst_trx_ids:
        if p < node.theta(env.now):
            print("====Burst traffic!====, from node", node.nodeid, "at:", env.now)
            nodes_burst_trx_ids.append(node.nodeid)
        else:
            wtime = random.expovariate(node.get_rate())

            print("[DEBUG] wtime non burst traffic node:", wtime)

            # fix bug for nodes affected by the effect that stay on idle during the event because of low arrival rate
            if node.nodeid in on_fire_ids or node.nodeid in on_danger_ids:
                if node.nodeid not in nodes_burst_trx_ids:

                    if wtime + env.now >= t_e + BURST_DURATION and env.now < t_e + BURST_DURATION:
                        if t_e <= env.now <= t_e + BURST_DURATION:
                            # wtime = env.now - t_e #+ BURST_DURATION*3/4
                            # wtime = env.now - t_e  # + random.uniform(1, BURST_DURATION / 10)
                            # yield env.timeout(random.uniform(1,BURST_DURATION/10))
                            continue
                        else:
                            # wtime = t_e - env.now #+ BURST_DURATION*3/4
                            wtime = t_e - env.now  # + random.uniform(1, BURST_DURATION / 10)
                            yield env.timeout(wtime)
                            continue
                    # nodes_burst_trx_ids.append(node.nodeid)
                    #     continue

            # print("----normal traffic----, wait:", wtime, "at:", env.now)
            yield env.timeout(wtime)

        # time sending and receiving
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

        yield env.timeout(node.packet.rectime)

        if node.packet.lost:
            # global nrLost
            nrLost = nrLost + 1
        if node.packet.collided == 1:
            # global nrCollisions
            nrCollisions = nrCollisions + 1
        if node.packet.collided == 0 and not node.packet.lost:
            # global nrReceived
            nrReceived = nrReceived + 1
        if node.packet.processed == 1:
            # global nrProcessed
            nrProcessed = nrProcessed + 1

        # complete packet has been received by base station
        # can remove it
        if node in packetsAtBS:
            packetsAtBS.remove(node)
            # reset the packet
        node.packet.collided = 0
        node.packet.processed = 0
        node.packet.lost = False

        # global prev_time, pkts_sent, pkts_gen, pkts_sent_prev, pkts_gen_prev, sumsent
        sumsent = sum(s.sent for s in nodes)

        if env.now - prev_time >= 100:
            pkts_gen.append(sumsent - pkts_gen_prev)
            pkts_sent.append(nrReceived - pkts_sent_prev)
            time.append(env.now / 1000)
            prev_time = env.now
            pkts_gen_prev = sumsent
            pkts_sent_prev = nrReceived

            if PROG_BAR:
                myProgressBar.progress(int(env.now))


nodes = []
packetsAtBS = []
env = simpy.Environment()

# maximum number of packets the BS can receive at the same time
maxBSReceives = 8

# max distance: 300m in city, 3000 m outside (5 km Utz experiment)
# also more unit-disc like according to Utz
bsId = 1
nrCollisions = 0
nrReceived = 0
nrProcessed = 0
nrLost = 0

Ptx = 14
gamma = 2.08
d0 = 1000.0
var = 0  # variance ignored for now
Lpld0 = 127.41
GL = 0

#
# "main" program
#
on_fire_ids = []
on_danger_ids = []
normal_ids = []
nodes_burst_trx_ids = []
global t_e  # event start time
global myProgressBar

global pkts_sent, pkts_gen, time, prev_time, pkts_gen_prev, pkts_sent_prev
pkts_sent = []
pkts_gen = []
time = []
prev_time = 0
pkts_gen_prev = 0
pkts_sent_prev = 0

# event epicenter
evep_x = 1500
evep_y = 1500
d_th = 150  # cut-off distance
W = 200  # width of window

Up = 4000  # event propagation speed
BURST_DURATION = 1000

# event driven traffic
EVENT_TRAFFIC = True
T_MODEL = 'RAISEDCOS'
# T_MODEL = 'DECAYINGEXP'
a = 0.005

# progressbar flag
PROG_BAR = False

if not EVENT_TRAFFIC:
    Up = '-'

# random.seed(0)


# get arguments
if len(sys.argv) >= 6:
    nrNodes = int(sys.argv[1])
    avgSendTime = int(sys.argv[2])
    experiment = int(sys.argv[3])
    simtime = int(sys.argv[4])
    payloadlen = int(sys.argv[5])
    if len(sys.argv) > 6:
        full_collision = bool(int(sys.argv[6]))
    print("Nodes:", nrNodes)
    print("AvgSendTime (exp. distributed):", avgSendTime)
    print("Experiment: ", experiment)
    print("Simtime: ", simtime)
    print("payload size: ", payloadlen)
    print("Full Collision: ", full_collision)

    if PROG_BAR:
        myProgressBar = ProgressBar(nElements=100, nIterations=simtime)

else:
    print("usage: ./loraDir nrNodes avgSendTime experimentNr simtime payloadsize [full_collision]")
    print("experiment 0 and 1 use 1 frequency only")
    exit(-1)

if EVENT_TRAFFIC:
    t_e = simtime / 2
    print("Time of event:", t_e)
    print("Event duration:", BURST_DURATION)

sensi = np.array([sf7, sf8, sf9, sf10, sf11, sf12])
minsensi = -132.5

if experiment in [0, 1, 4]:
    minsensi = sensi[5, 2]  # 5th row is SF12, 2nd column is BW125
elif experiment == 2:
    minsensi = -112.0  # no experiments, so value from datasheet
elif experiment == 3:
    minsensi = np.amin(sensi)  # Experiment 3 can use any setting, so take minimum
# elif experiment == 5:
#     minsensi = np.amin(sensi)  # Experiment 5 can use any setting, so take minimum

Lpl = Ptx - minsensi
print("amin", minsensi, "Lpl", Lpl)
maxDist = d0 * (math.e ** ((Lpl - Lpld0) / (10.0 * gamma)))
print("maxDist:", maxDist)

# base station placement
bsx = maxDist + 10
bsy = maxDist + 10
xmax = bsx + maxDist + 20
ymax = bsy + maxDist + 20

for i in range(0, nrNodes):
    # myNode takes period (in ms), base station id packetlen (in Bytes)
    # 1000000 = 16 min
    node = myNode(i, bsId, avgSendTime, payloadlen)

    nodes.append(node)
    if EVENT_TRAFFIC:
        env.process(transmit_event(env, node))
    else:
        env.process(transmit(env, node))

# prepare show

# start simulation
env.run(until=simtime)

nodes_burst_trx_ids = set(nodes_burst_trx_ids)

# print(stats and save into file
print("nrCollisions ", nrCollisions)

# compute energy
# Transmit consumption in mA from -2 to +17 dBm
TX = [22, 22, 22, 23,  # RFO/PA0: -2..1
      24, 24, 24, 25, 25, 25, 25, 26, 31, 32, 34, 35, 44,  # PA_BOOST/PA1: 2..14
      82, 85, 90,  # PA_BOOST/PA1: 15..17
      105, 115, 125]  # PA_BOOST/PA1+PA2: 18..20
# mA = 90    # current draw for TX = 17 dBm
V = 3.0  # voltage XXX
sent = sum(n.sent for n in nodes)
# energy = sum(node.packet.rectime * TX[int(node.packet.txpow) + 2] * V * node.sent for node in nodes) / 1e6

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
        Up) + " " + str(pdr) + " " + str(der2)
else:
    res = "#nrNodes nrCollisions nrTransmissions OverallEnergy Up PDR DER2\n" + str(nrNodes) + " " + str(
        nrCollisions) + " " + str(sent) + " " + str(energy) + " " + str(Up) + " " + str(pdr) + " " + str(der2)
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
    fieldnames = ['#nrNodes', 'nrCollisions', 'nrTransmissions', 'OverallEnergy', 'Up', 'PDR']
    if create_csv:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(fieldnames)
    else:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow([str(nrNodes), str(nrCollisions), str(sent), str(energy), str(Up), str(pdr)])
csv_file.close()

fname_csv_gen_sen = "generated_delivered_v=" + str(Up) + "ms_n=" + str(nrNodes) + ".csv"
print(fname_csv_gen_sen)
create_csv_gen_sen = True
if os.path.isfile(fname_csv_gen_sen):
    create_csv_gen_sen = False
else:
    create_csv_gen_sen = True
with open(fname_csv_gen_sen, mode='a+', newline='') as csv_file:
    fieldnames = ['time' + str(Up), '#pkts_gen' + str(Up), '#pkts_sent' + str(Up)]
    if create_csv_gen_sen:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(fieldnames)
    else:
        writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    for i in range(len(time)):
        writer.writerow([time[i], pkts_gen[i], pkts_sent[i]])
csv_file.close()

# with open('nodes.txt','w') as nfile:
#     for n in nodes:
#         nfile.write("{} {} {}\n".format(n.x, n.y, n.nodeid))
# with open('basestation.txt', 'w') as bfile:
#     bfile.write("{} {} {}\n".format(bsx, bsy, 0))


winsound.Beep(540, 1000)
