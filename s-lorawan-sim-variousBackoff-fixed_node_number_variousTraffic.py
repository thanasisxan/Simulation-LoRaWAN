import simpy
import numpy as np
import queue
import random

TIMESLOT = 1  # The timeslot duration
RX1_DELAY = 0.35  # rx1 Delay before waiting for receiving Acknowledgement(downlink)
UPLINK_TIME = 0.5  # Time for the payload
ACK_TIME = 0.15  # ACK packet time of air

SLOTTED_ALOHA = True
# SLOTTED_ALOHA = False

# Backoff strategies
# Only one of the next 4 flags (BEB, ECA, EFB, EBEB, EIED, ASB) should be set to True!

# If all flags are set to False a simple random uniform backoff time is chosen between (0,63)
BEB = True  # Binary Exponential Backoff strategy
ECA = False  # Enhanced Collision Avoidance strategy
EFB = False  # Enhanced Fibonacci Backoff strategy
EBEB = False  # Enhanced Binary Exponential Backoff strategy
EIED = False  # Exponential Increase Exponential Decrease
ASB = False  # Adaptively Scaled Backoff strategy
Fixed_CW = 63

# Universal Backoff parameters
maxR = 6
maxB = 5
CW_min = 2
CW_max = 1023
r_d = np.sqrt(2)
r_1 = 2

Q = 5  # Queue length
L = 5 / 3000  # Poisson Arrival rate
# MAX_TOTAL_TIMESLOTS = 14400 * TIMESLOT
MAX_TOTAL_TIMESLOTS = 14400 * TIMESLOT
TOTAL_LORA_ENDNODES = 300
BURSTY_TRAFFIC_NODES = 100
L_NODE_BURSTY = [0.0 for _ in range(TOTAL_LORA_ENDNODES)]

for _ in range(TOTAL_LORA_ENDNODES - BURSTY_TRAFFIC_NODES):
    L_NODE_BURSTY[_] = L

for _ in range((TOTAL_LORA_ENDNODES - BURSTY_TRAFFIC_NODES), TOTAL_LORA_ENDNODES):
    L_NODE_BURSTY[_] = 10 / 3000

Nodes_col_flag = [0 for _ in range(TOTAL_LORA_ENDNODES)]
GW_col_flag = [0 for _ in range(TOTAL_LORA_ENDNODES)]
total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0
trx_attempts = 1
total_delay = 0
dropped_packets = 0

P_success = 0  # chance of successfully transmitting a packet


# np.random.seed(2392)

# next fibonacci number approximation - calculation in linear time
def nextFibonacci(n):
    a = n * (1 + np.sqrt(5)) / 2.0
    return round(a)


# previous fibonacci number approximation - calculation in linear time
def previousFibonacci(n):
    a = n / ((1 + np.sqrt(5)) / 2.0)
    return round(a)


class Packet:
    def __init__(self, num: int):
        self.id = num
        self.owner = None
        self.re_trx_count = 0
        self.arrival_time = 0
        self.trx_finish_time = 0
        self.gw_sent_ack = False


class LoraGateway:
    def __init__(self, env: simpy.Environment):
        self.env = env

    def receivepacket(self, packet: Packet, from_node):
        global Nodes_col_flag
        global GW_col_flag

        print("( loraGateway ) Received Packet", packet.id, "from ( loraNode", packet.owner,
              ") at", self.env.now)

        Nodes_col_flag[from_node.id] = 1
        GW_col_flag[from_node.id] = 1
        # print(Nodes_col_flag[from_node.id])
        yield self.env.timeout(RX1_DELAY)
        if sum(Nodes_col_flag) < 2 and sum(GW_col_flag) < 2:
            print("( loraGateway ) Sent ACK for Packet", packet.id, "from ( loraNode", packet.owner,
                  ") at:", self.env.now)
            GW_col_flag[from_node.id] = 0
            Nodes_col_flag[from_node.id] = 0
            packet.gw_sent_ack = True
        else:
            print("Collision (gw)")
            Nodes_col_flag[from_node.id] = 1
            GW_col_flag[from_node.id] = 1
            packet.gw_sent_ack = False
            # collision flag


class LoraNode:
    def __init__(self, env: simpy.Environment, id: int):
        self.env = env
        self.id = id
        self.CW = CW_min
        self.k = np.random.uniform(0, self.CW)
        self.bSlot = self.k
        self.r = 0
        self.s = 0
        self.f_b = 0
        self.f_c = 0
        self.S_factor = 1
        self.p_c = 0
        self.ebeb_counter = 0
        self.queue = queue.Queue(Q)

    def sendpacket(self, gateway: LoraGateway):
        global total_packets_sent
        global trx_attempts
        global Nodes_col_flag
        global GW_col_flag
        global total_delay
        global CW_min
        global CW_max
        global r_d
        global r_1
        global lora_nodes_created
        global maxB
        global maxR
        global Fixed_CW

        if not self.queue.empty():
            # Get packet for transmission without removing it from the queue
            packet = self.queue.queue[0]
            # packet = self.queue.get()

            if self.env.now % 1 == 0:
                if packet.re_trx_count == 0:
                    print("( loraNode", self.id, ") The Packet", packet.id, "from ( loraNode", packet.owner,
                          ") arrived exactly at the start of a timeslot, transmitting at:", self.env.now)
            else:
                if SLOTTED_ALOHA:
                    # The packet didn't arrive at the start of a timeslot,
                    # attempt to transmit at the start of the next timeslot
                    yield wait_next_timeslot(self.env)
                if packet.re_trx_count == 0:
                    print("( loraNode", self.id, ") Attempt to transmit Packet", packet.id, "from ( loraNode",
                          packet.owner,
                          ") at timeslot:", self.env.now)
                else:
                    print("( loraNode", self.id, ") Retransmitting Packet", packet.id, "from ( loraNode",
                          packet.owner, ") at timeslot:", self.env.now)

            trx_attempts += 1

            Nodes_col_flag[self.id] = 1
            yield self.env.timeout(UPLINK_TIME)  # time to transmit the payload
            GW_col_flag[self.id] = 1
            yield self.env.process(gateway.receivepacket(packet, self))  # timeout(RX1_DELAY) at receivepacket (GW)

            if sum(Nodes_col_flag) < 2 and sum(GW_col_flag) < 2 and packet.gw_sent_ack:
                # Successful transmission
                yield self.env.timeout(ACK_TIME)  # time to complete the reception of Acknowledgment(Downlink)

                # # Remove the packet from the queue after successful transmission
                # self.queue.get()

                # print("Q length:", self.queue.qsize())
                Nodes_col_flag[self.id] = 0
                GW_col_flag[self.id] = 0
                total_packets_sent += 1
                print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", self.env.now)
                packet.trx_finish_time = self.env.now
                print("Packet", packet.id, "finish trx time:", packet.trx_finish_time)
                total_delay += packet.trx_finish_time - packet.arrival_time
                print("Delay for packet", packet.id, ":", packet.trx_finish_time - packet.arrival_time)
                self.r = 0
                self.s = 0
                self.S_factor = 1
                self.f_b = 0
                self.f_c = 0
                if BEB:
                    self.CW = CW_min
                    # self.k = np.random.uniform(0, self.CW)
                elif ECA:
                    self.k = CW_min / 2 - 1
                    # self.k = np.random.uniform(0, self.CW)
                elif EIED:
                    self.CW = min(self.CW / r_d, CW_max)
                    # self.k = np.random.uniform(0, self.CW)
                elif ASB:
                    self.CW = CW_min
                    # self.k = np.random.uniform(0, self.CW)
                elif EFB:
                    # self.CW = max(previousFibonacci(self.CW), CW_min)
                    self.CW = min(previousFibonacci(self.CW), CW_max)
                    # self.k = np.random.uniform(0, self.CW)
                elif EBEB:
                    # self.CW = CW_min
                    # if not self.CW < (1 / np.sqrt(CW_min)) * CW_min:
                    #     self.CW = self.CW + (CW_max / self.CW) * CW_min
                    if self.ebeb_counter < CW_min:
                        self.ebeb_counter += 1
                        if self.CW > CW_min:
                            self.CW = self.CW - CW_min
                        else:
                            self.CW = -2
                        if self.CW < (1 / np.sqrt(CW_min)) * CW_min:
                            self.CW = (1 / np.sqrt(CW_min)) * CW_min
                    else:
                        self.ebeb_counter = 1
                        self.CW = self.CW + (CW_max / self.CW) * CW_min
                        if self.CW > CW_max:
                            self.CW = CW_max
                    # self.k = np.random.uniform(0, self.CW)
                else:
                    self.CW = min(np.random.uniform(0, Fixed_CW), CW_max)
                    # self.k = np.random.uniform(0, self.CW)
                # self.k = np.random.uniform(0, self.CW)

                # Remove the packet from the queue after successful transmission
                t = self.queue.get()
                print("pkt", t.id, "removed")

            else:
                print('Collision!!!--n')
                Nodes_col_flag[self.id] = 0
                GW_col_flag[self.id] = 0
                yield self.env.process(self.retransmitpacket(gateway, packet))

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        global CW_min
        global CW_max
        global r_d
        global r_1
        global lora_nodes_created
        global maxB
        global maxR
        global Fixed_CW
        global dropped_packets

        packet.re_trx_count += 1
        n = lora_nodes_created
        self.s = min(self.s + 1, maxB)
        self.r = self.r + 1
        self.f_c = 1
        self.f_b += 1

        # print("Q length:", self.queue.qsize())
        self.k = np.random.uniform(0, self.CW)
        if BEB:
            # self.CW = min(2 ** self.s * (CW_min + 1) - 1, CW_max)
            self.CW = min(2 ** (self.r + 1), CW_max)
        elif ECA:
            # on collision ECA backoff time is equal to that Binary Exponential Backoff strategy
            self.CW = min(2 ** (self.r + 1), CW_max)
            # self.CW = min(2 ** self.s * (CW_min + 1) - 1, CW_max)
            if self.r == 1:
                self.k = CW_min / 2 - 1
        elif EIED:
            self.CW = min(r_1 * CW_min - 1, CW_max)
        elif ASB:
            self.p_c = (self.f_b + self.f_c) / self.bSlot
            self.S_factor = self.S_factor + round(n * self.p_c / self.S_factor)
            self.CW = min(self.S_factor * CW_min - 1, CW_max)
        elif EFB:
            self.CW = min(nextFibonacci(self.CW), CW_max)
            print("CW to be used after:", self.CW)
        elif EBEB:
            self.CW = min(2 ** self.r, CW_max)
            # self.CW = CW_min
            # self.CW = min(self.CW + (CW_max / self.CW) * CW_min, CW_max)
        else:
            self.CW = min(np.random.uniform(0, Fixed_CW), CW_max)

        # self.k = np.random.uniform(0, self.CW)
        if packet.re_trx_count > maxR:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            print("Dropping packet...")
            # print("Q:", self.queue.qsize())
            dropped_packets += 1
            # Remove the packet from the queue after maximum retransmissions
            if self.queue.empty():
                # self.queue.queue.clear()
                print("q size 0")
            else:
                self.queue.get()
            # return
        else:
            print("( loraNode", self.id, ") Backoff_Time:", self.k, "for Packet", packet.id, "(",
                  packet.re_trx_count, "collisions so far for this packet ) (", self.r,
                  "collisions so far for this loraNode)")
            yield self.env.timeout(self.k)
            yield self.env.process(self.sendpacket(gateway))


def loranode_arrival_process(env: simpy.Environment, current_lnode: LoraNode):
    global total_packets_created
    global Nodes_col_flag
    global P_success
    global trx_attempts
    global dropped_packets

    while True:

        # L is λ, the arrival rate in Poisson process

        IAT = random.expovariate(L)
        # print("IAT:", IAT)
        yield env.timeout(IAT)
        total_packets_created += 1
        if not current_lnode.queue.full():
            pkt = Packet(total_packets_created)
            pkt.owner = current_lnode.id
            pkt.arrival_time = env.now

            current_lnode.queue.put(pkt)
            print("( loraNode", current_lnode.id, ") Packet", pkt.id, "arrived at:", pkt.arrival_time)
            print("( loraNode", current_lnode.id, ") Queue length:", current_lnode.queue.qsize())
        else:
            dropped_packets += 1
            print("( loraNode", current_lnode.id, ") Queue Full! Dropping Packet...")

        env.process(current_lnode.sendpacket(l_gw))


def loranode_transmit_process(env: simpy.Environment, current_lnode: LoraNode):
    while not current_lnode.queue.empty():
        yield current_lnode.sendpacket(l_gw)
        # print("\n\n=================", current_lnode.id,"\n\n")


def wait_next_timeslot(env: simpy.Environment):
    if SLOTTED_ALOHA:
        # wait for the start of the next timeslot
        return env.timeout(((env.now // 1 + 1) * TIMESLOT) - env.now)
    else:
        # PURE ALOHA transmit immediately
        return env.timeout(0)


def setup(env: simpy.Environment):
    global lora_nodes_created

    yield env.timeout(1)  # start at 1 to eliminate low env.now number bug at statistics calculation
    for i in range(TOTAL_LORA_ENDNODES):
        # print("\n\n\n------====== Creating a new LoRa Node ======------\n\n\n")
        lnode = LoraNode(env, lora_nodes_created)
        lora_nodes_created += 1
        env.process(loranode_arrival_process(env, lnode))
        env.process(loranode_transmit_process(env, lnode))


env = simpy.Environment()

l_gw = LoraGateway(env)

env.process(setup(env))

env.run(until=MAX_TOTAL_TIMESLOTS)

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
# print("Lora nodes:", lora_nodes_created)
# print("λ:", L)
print("Packet dorp rate:", dropped_packets / total_packets_created)
print("Trx attempts:", trx_attempts)
# print("Sucessful transmission prob.:", total_packets_sent / trx_attempts)

print("Traffic load (packets created/slot):", total_packets_created / MAX_TOTAL_TIMESLOTS)
print("Channel load (transmission attempts/slot)", trx_attempts / MAX_TOTAL_TIMESLOTS)
print("Throughput (packets sent/slot):", total_packets_sent / MAX_TOTAL_TIMESLOTS)
print("Total delay:", total_delay)
print("Avg. delay:", total_delay / total_packets_sent)

print("L array:", L_NODE_BURSTY)
