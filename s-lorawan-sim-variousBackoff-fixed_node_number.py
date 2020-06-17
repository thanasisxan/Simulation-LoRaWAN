import simpy
import numpy as np
import queue

TIMESLOT = 1  # The timeslot duration
RX1_DELAY = 0.3  # rx1 Delay before waiting for receiving Acknowledgement(downlink)
UPLINK_TIME = 0.5  # Time for the payload
ACK_TIME = 0.15  # ACK packet time of air

SLOTTED_ALOHA = True
# SLOTTED_ALOHA = False

# Backoff strategies
# Only one of the next 4 flags (BEB, ECA, EIED, ASB, EFB) should be set to True!
# If all flags are set to False a simple random uniform backoff time is chosen between (0,15)
BEB = True  # Binary Exponential Backoff strategy
ECA = False  # Enhanced Collision Avoidance strategy
EFB = False  # Enhanced Fibonacci Backoff strategy
EBEB = False  # Enhanced Binary Exponential Backoff strategy
EIED = False  # Exponential Increase Exponential Decrease
ASB = False  # Adaptively Scaled Backoff strategy

# Universal Backoff parameters
maxR = 6
maxB = 6
CW_min = 2
CW_max = 1023
r_d = np.sqrt(2)
r_1 = 2

Q = 5
MAX_TOTAL_TIMESLOTS = 14400 * TIMESLOT
TOTAL_LORA_ENDNODES = 300

Nodes_col_flag = [0 for _ in range(TOTAL_LORA_ENDNODES)]
total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0
trx_attempts = 0
total_delay = 0

G = [0]  # Traffic load
S = [0]  # Throughput
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


class LoraGateway:
    def __init__(self, env: simpy.Environment):
        self.env = env

    def receivepacket(self, packet: Packet, from_node):
        global Nodes_col_flag
        print("( loraGateway ) Received Packet", packet.id, "from ( loraNode", packet.owner,
              ") at", self.env.now)

        if sum(Nodes_col_flag) < 2:
            print("( loraGateway ) Sending ACK for Packet", packet.id, "from ( loraNode", packet.owner,
                  ") at:", self.env.now)
            # print(from_node.id)
            Nodes_col_flag[from_node.id] = 1
            # print(Nodes_col_flag[from_node.id])
            yield self.env.timeout(RX1_DELAY)
            Nodes_col_flag[from_node.id] = 0
            # print(Nodes_col_flag[from_node.id])
        else:
            print("Collision (gw)")
            Nodes_col_flag[from_node.id] = 1


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
        self.last_transmission_time = 0
        self.queue = queue.Queue(Q)

    def sendpacket(self, gateway: LoraGateway):
        global total_packets_sent
        global trx_attempts
        global Nodes_col_flag
        global total_delay

        if not self.queue.empty():
            # Get packet for transmission without removing it from the queue
            packet=self.queue.queue[0]

            if packet.re_trx_count == 0:
                print("( loraNode", self.id, ") Packet", packet.id, "created at:", self.env.now, "from ( loraNode",
                      packet.owner,
                      ")")
            if self.env.now % 1 == 0:
                if packet.re_trx_count == 0:
                    print("( loraNode", self.id, ") The Packet", packet.id, "from ( loraNode", packet.owner,
                          ") arrived exactly at the start of a timeslot, transmitting at:", self.env.now)
            else:
                # The packet didn't arrive at the start of a timeslot,
                # attempt to transmit at the start of the next timeslot
                yield wait_next_timeslot(self.env)
                if packet.re_trx_count == 0:
                    print("( loraNode", self.id, ") Attempt to transmit Packet", packet.id, "from ( loraNode", packet.owner,
                          ") at timeslot:", self.env.now)
                else:
                    print("( loraNode", self.id, ") Retransmitting Packet", packet.id, "from ( loraNode",
                          packet.owner, ") at timeslot:", self.env.now)

            trx_attempts += 1

            Nodes_col_flag[self.id] = 1
            yield self.env.timeout(UPLINK_TIME)  # time to transmit the payload
            yield self.env.process(gateway.receivepacket(packet, self))  # there is a timeout(RX1_DELAY) at receivepacket

            if sum(Nodes_col_flag) < 2:
                # Successful transmission
                yield self.env.timeout(ACK_TIME)  # time to complete the reception of Acknowledgment(Downlink)
                self.queue.get()
                print("Q length:",self.queue.qsize())
                Nodes_col_flag[self.id] = 0
                total_packets_sent += 1
                print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", self.env.now)
                packet.trx_finish_time = self.env.now
                print("Packet", packet.id, "finish trx time:", packet.trx_finish_time)
                total_delay = total_delay + (packet.trx_finish_time - packet.arrival_time)
                print("Delay for packet", packet.id, ":", packet.trx_finish_time - packet.arrival_time)
                self.r = 0
                self.s = 0
                self.S_factor = 1
                self.f_b = 0
                self.f_c = 0
                if BEB:
                    self.CW = CW_min
                    self.k = np.random.uniform(0, self.CW)
                elif ECA:
                    self.k = CW_min / 2 - 1
                elif EIED:
                    self.CW = min((self.CW / r_d), CW_max)
                    self.k = np.random.uniform(0, self.CW)
                elif ASB:
                    self.CW = CW_min
                    self.k = np.random.uniform(0, self.CW)
                elif EFB:
                    self.CW = max(previousFibonacci(self.CW), CW_min)
                    self.k = np.random.uniform(0, self.CW)
                elif EBEB:
                    if not self.CW < (1 / np.sqrt(CW_min)) * CW_max:
                        self.CW = self.CW + (CW_max / self.CW) * CW_min

            else:
                print('Collision!!!--n')
                Nodes_col_flag[self.id] = 0
                yield self.env.process(self.retransmitpacket(gateway, packet))

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        packet.re_trx_count += 1
        n = lora_nodes_created
        self.s = min(self.s + 1, maxB)
        self.r = self.r + 1
        self.f_c = 1

        print("Q length:",self.queue.qsize())

        if BEB:
            self.CW = min(2 ** self.s + 1, CW_max)
        elif ECA:
            # on collision ECA backoff time is equal to that Binary Exponential Backoff strategy
            self.CW = min(2 ** self.s + 1, CW_max)
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
            self.CW = min(2 ** self.s + 1, CW_max)
        else:
            self.CW = min(np.random.uniform(0, 15), CW_max)
        self.k = np.random.uniform(0, self.CW)

        if packet.re_trx_count > maxR:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            print("Dropping packet...")
            self.CW = CW_min
            return
        else:
            print("( loraNode", self.id, ") Backoff_Time:", self.k, "for Packet", packet.id, "(",
                  packet.re_trx_count, " collisions so far for this packet )")
            yield self.env.timeout(self.k)
            yield self.env.process(self.sendpacket(gateway))


def loranode_arrival_process(env: simpy.Environment, current_lnode: LoraNode):
    global total_packets_created
    global Nodes_col_flag

    global G
    global S
    global P_success
    global trx_attempts

    while True:
        # yield env.timeout(0.1)
        # L is λ, the arrival rate in Poisson process
        L = 1 / 3000
        P_arrival = np.random.exponential(L)
        P_q_add = np.random.random()

        if P_q_add <= P_arrival:
            pkt = Packet(total_packets_created)
            pkt.owner = current_lnode.id
            total_packets_created += 1
            pkt.arrival_time = env.now

            current_lnode.queue.put(pkt)
            # yield env.process(current_lnode.sendpacket(l_gw, pkt))

            # statistics calculation
            G.append(trx_attempts / (env.now / UPLINK_TIME))
            # G.append(total_packets_created / (env.now / UPLINK_TIME))
            P_success = total_packets_sent / total_packets_created
            # S.append(G[-1] * P_success)
            S.append(total_packets_sent / (env.now / UPLINK_TIME))

            if SLOTTED_ALOHA:
                yield wait_next_timeslot(env)
        else:
            Nodes_col_flag[current_lnode.id] = 0
            yield wait_next_timeslot(env)
            if not SLOTTED_ALOHA:
                yield env.timeout(5)


def loranode_transmit_process(env: simpy.Environment, current_lnode: LoraNode):
    while True:
        yield env.timeout(np.random.random())
        if not current_lnode.queue.empty():
            yield env.process(current_lnode.sendpacket(l_gw))
        # yield env.timeout(3)
        # print("\n\n=================", current_lnode.id,"\n\n")


def wait_next_timeslot(env: simpy.Environment):
    if SLOTTED_ALOHA:
        # wait for the start of the next timeslot
        return env.timeout(((env.now // 1 + 1) * TIMESLOT) - env.now)
    else:
        # PURE ALOHA transmit immediately
        return env.timeout(0)


loraNodes = []


def setup(env: simpy.Environment):
    global G
    global lora_nodes_created

    yield env.timeout(1)  # start at 1 to eliminate low env.now number bug at statistics calculation
    for _ in range(TOTAL_LORA_ENDNODES):
        print("\n\n\n------====== Creating a new LoRa Node ======------\n\n\n")
        lnode = LoraNode(env, lora_nodes_created)
        lora_nodes_created += 1
        loraNodes.append(lnode)
        env.process(loranode_arrival_process(env, lnode))
        env.process(loranode_transmit_process(env, lnode))


env = simpy.Environment()

l_gw = LoraGateway(env)

env.process(setup(env))

env.run(until=MAX_TOTAL_TIMESLOTS)

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
print("Lora nodes:", lora_nodes_created)

print("Trx attempts:", trx_attempts)

print("Mean G - channel traffic load:", np.mean(G))
print("Last G - channel traffic load:", G[-1])
# print("Mean S(G) - throughput:", np.mean(S))
# print("MAX S(G) - throughput:", max(S))
print("Traffic load (packets created/slot):", total_packets_created / MAX_TOTAL_TIMESLOTS)
print("Throughput (packets sent/slot):", total_packets_sent / MAX_TOTAL_TIMESLOTS)
print("Total delay:", total_delay)
print("Avg. delay:", total_delay / total_packets_sent)
