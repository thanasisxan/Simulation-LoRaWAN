import simpy
import matplotlib.pyplot as plt
import numpy as np

TIMESLOT = 1  # The timeslot duration
RX1_DELAY = 0.85  # rx1 Delay before waiting for receiving Acknowledgement(downlink)
UPLINK_TIME = 1  # Time for the payload
ACK_TIME = 0.2  # ACK packet time of air

SLOTTED_ALOHA = True
# SLOTTED_ALOHA = False

# Backoff strategies
# Only one of the next 4 flags (BEB, ECA, EIED, ASB, EFB) should be set to True!
# If all flags are set to False a simple random uniform backoff time is chosen between (0,15)
BEB = False  # Binary Exponential Backoff strategy
ECA = False  # Enhanced Collision Avoidance strategy
EFB = False  # Enhanced Fibonacci Backoff strategy
EBEB = False  # Enhanced Binary Exponential Backoff strategy
EIED = False  # Exponential Increase Exponential Decrease
ASB = True  # Adaptively Scaled Backoff strategy


# Universal Backoff parameters
maxR = 6
maxB = 5
CW_min = 2
CW_max = 1023
r_d = np.sqrt(2)
r_1 = 2

MAX_TOTAL_TIMESLOTS = 144000 * TIMESLOT

total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0
trx_attempts = 0

G = [0.001]  # Traffic load
S = [0]  # Throughput
P_success = 0  # chance of successfully transmitting a packet

np.random.seed(2392)


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


class LoraGateway:
    def __init__(self, env: simpy.Environment):
        self.env = env

    def receivepacket(self, packet: Packet):
        print("( loraGateway ) Received Packet", packet.id, "from ( loraNode", packet.owner,
              ") at", self.env.now)
        # after uplink time wait rx1Delay, before getting in receiving the Acknowledgement state at the LoraNode
        yield self.env.timeout(RX1_DELAY)
        print("( loraGateway ) Sending ACK for Packet", packet.id, "from ( loraNode", packet.owner,
              ") at:", self.env.now)


class LoraNode:
    def __init__(self, env: simpy.Environment, channel: simpy.Resource, id: int):
        self.env = env
        self.channel = channel
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

    def sendpacket(self, gateway: LoraGateway, packet: Packet):
        global total_packets_sent
        global trx_attempts

        if packet.re_trx_count == 0:
            print("( loraNode", self.id, ") Packet", packet.id, "created at:", self.env.now, "from ( loraNode", packet.owner,
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
        req = self.channel.request()  # request the channel in order to transmit
        results = yield req | self.env.timeout(0)  # check if channel is busy

        if req in results:
            yield self.env.timeout(UPLINK_TIME)  # time to transmit the payload
            yield self.env.process(gateway.receivepacket(packet))  # there is a timeout(RX1_DELAY) at receivepacket
            yield self.env.timeout(ACK_TIME)  # time to complete the reception of Acknowledgment(Downlink)

            print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", self.env.now)

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

            total_packets_sent += 1
        else:
            print('Collision!!!--n')
            yield self.env.process(self.retransmitpacket(gateway, packet))

        yield self.channel.release(req)  # channel is free after transmission or retransmission backoff time

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        packet.re_trx_count += 1
        n = lora_nodes_created
        self.s = min(self.s + 1, maxB)
        self.r = self.r + 1

        print("( loraNode", self.id, ") Backoff_Time:", self.k, "for Packet", packet.id, "(",
              packet.re_trx_count, " collisions so far for this packet )")
        if packet.re_trx_count > maxR:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            print("Dropping packet...")
            self.CW = CW_min
            return
        else:
            yield self.env.timeout(self.k)
            yield self.env.process(self.sendpacket(gateway, packet))

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


def loranode_process(env: simpy.Environment, channel: simpy.Resource):
    global total_packets_created
    global lora_nodes_created

    global G
    global S
    global P_success
    global trx_attempts

    current_lnode = LoraNode(env, channel, lora_nodes_created)
    lora_nodes_created += 1
    while max(G) < 3.9 and lora_nodes_created < 1000:
        # L is λ, the arrival rate in Poisson process
        # packet generation on Lora networks based on traffic load (G)
        L = G[-1]
        P_arrival = np.exp(-L) * L
        P_transmit = np.random.random()
        if P_transmit <= P_arrival:
            pkt = Packet(total_packets_created)
            pkt.owner = current_lnode.id
            total_packets_created += 1

            yield env.process(current_lnode.sendpacket(l_gw, pkt))

            # statistics calculation
            G.append(trx_attempts / (env.now / UPLINK_TIME))
            P_success = total_packets_sent / total_packets_created
            S.append(G[-1] * P_success)
            # if SLOTTED_ALOHA:
            #     yield wait_next_timeslot(env)
        else:
            yield wait_next_timeslot(env)
            if not SLOTTED_ALOHA:
                yield env.timeout(5)


def wait_next_timeslot(env: simpy.Environment):
    if SLOTTED_ALOHA:
        # wait for the start of the next timeslot
        return env.timeout(((env.now // 1 + 1) * TIMESLOT) - env.now)
    else:
        # PURE ALOHA transmit immediately
        return env.timeout(0)


def setup(env: simpy.Environment):
    global G
    global lora_nodes_created

    yield env.timeout(10)  # start at 10 to eliminate low env.now number bug at statistics calculation
    env.process(loranode_process(env, channel))
    while max(G) < 3.9 and lora_nodes_created < 1000:
        # print("\n\n\n------====== Creating a new LoRa Node ======------\n\n\n")
        env.process(loranode_process(env, channel))
        yield env.timeout(70)


env = simpy.Environment()

# The channel is modeled as a shared resource with capacity=1,
# as only one channel exists in our simulation which all nodes want to access when transmitting
channel = simpy.Resource(env, 1)
l_gw = LoraGateway(env)

env.process(setup(env))
env.run(until=MAX_TOTAL_TIMESLOTS)

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
print("Lora nodes:", lora_nodes_created)

print("Mean G - traffic load:", np.mean(G))
print("MAX S(G) - throughput:", max(S))

if SLOTTED_ALOHA:
    plt.plot(G, S, 'r:')
    if BEB:
        plt.title("Slotted LoRaWAN Protocol - Binary Exponential Backoff")
    elif ECA:
        plt.title("Slotted LoRaWAN Protocol - Enhanced Collision Avoidance")
    elif EIED:
        plt.title("Slotted LoRaWAN Protocol - Exponential Increase Exponential Decrease")
    elif ASB:
        plt.title("Slotted LoRaWAN Protocol - Adaptively Scaled Backoff")
    elif EFB:
        plt.title("Slotted LoRaWAN Protocol - Enhanced Fibonacci Backoff")
    elif EBEB:
        plt.title("Slotted LoRaWAN Protocol - Enhanced Binary Exponential Backoff")
    else:
        plt.title("Slotted LoRaWAN Protocol - Simple Uniform Backoff")

else:
    plt.plot(G, S, 'b:')
    plt.title("LoRaWAN Protocol")

plt.xlabel("G - traffic load")
plt.ylabel("S(G) - throughput")
plt.show()

data = np.array([G, S])
data = data.T

if BEB:
    datafile_path = "BEB.txt"
elif ECA:
    datafile_path = "ECA.txt"
elif EIED:
    datafile_path = "EIED.txt"
elif ASB:
    datafile_path = "ASB.txt"
elif EFB:
    datafile_path = "EFB.txt"
elif EBEB:
    datafile_path = "EBEB.txt"
else:
    datafile_path = "UB.txt"

with open(datafile_path, 'w+') as datafile_id:
    np.savetxt(datafile_id, data, fmt=['%f', '%f'])
