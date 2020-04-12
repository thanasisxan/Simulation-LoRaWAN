import simpy
import matplotlib.pyplot as plt
import numpy as np

# from scipy import interpolate

TIMESLOT = 1  # The timeslot duration
RX1_DELAY = 0.85  # rx1 Delay before waiting for receiving Acknowledgement(downlink)
UPLINK_TIME = 1  # Time for the payload
ACK_TIME = 0.2  # ACK packet time of air

SLOTTED_ALOHA = True
# SLOTTED_ALOHA = False

MAX_TOTAL_TIMESLOTS = 7200 * TIMESLOT

total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0
trx_attempts = 0

G = [0.001]  # Traffic load
S = [0]  # Throughput
P_success = 0  # chance of successfully transmitting a packet


np.random.seed(2392)  # keep only for getting the same results-no randomness in each run


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
              ") at", env.now)
        # after uplink time wait rx1Delay, before getting in receiving the Acknowledgement state at the LoraNode
        yield env.timeout(RX1_DELAY)
        print("( loraGateway ) Sending ACK for Packet", packet.id, "from ( loraNode", packet.owner,
              ") at:", env.now)


class LoraNode:
    def __init__(self, env: simpy.Environment, channel: simpy.Resource, id: int):
        self.env = env
        self.channel = channel
        self.id = id

    def sendpacket(self, gateway: LoraGateway, packet: Packet):
        global total_packets_sent
        global trx_attempts

        if packet.re_trx_count == 0:
            print("( loraNode", self.id, ") Packet", packet.id, "created at:", env.now, "from ( loraNode", packet.owner,
                  ")")
        if env.now % 1 == 0:
            if packet.re_trx_count == 0:
                print("( loraNode", self.id, ") The Packet", packet.id, "from ( loraNode", packet.owner,
                      ") arrived exactly at the start of a timeslot, transmitting at:", env.now)
        else:
            # The packet didn't arrive at the start of a timeslot,
            # attempt to transmit at the start of the next timeslot
            yield wait_next_timeslot(env)
            if packet.re_trx_count == 0:
                print("( loraNode", self.id, ") Attempt to transmit Packet", packet.id, "from ( loraNode", packet.owner,
                      ") at timeslot:", env.now)
            else:
                print("( loraNode", self.id, ") Retransmitting Packet", packet.id, "from ( loraNode",
                      packet.owner, ") at timeslot:", env.now)

        trx_attempts += 1
        req = channel.request()  # request the channel in order to transmit
        results = yield req | env.timeout(0)  # check if channel is busy

        if req in results:
            yield env.timeout(UPLINK_TIME)  # time to transmit the payload
            yield env.process(gateway.receivepacket(packet))  # there is a timeout(RX1_DELAY) at receivepacket
            yield env.timeout(ACK_TIME)  # time to complete the reception of Acknowledgment(Downlink)

            print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", env.now)
            total_packets_sent += 1
        else:
            print('Collision!!!--n')
            yield env.process(self.retransmitpacket(gateway, packet))

        yield channel.release(req)  # channel is free after transmission or retransmission backoff time

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        RandomBackoffTime = np.random.uniform(1, 25)  # wait random amount of time between 1 and 15
        print("( loraNode", self.id, ") Random Backoff Time:", RandomBackoffTime, "for Packet", packet.id)
        packet.re_trx_count += 1
        if packet.re_trx_count > 4:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            return
        else:
            yield env.timeout(RandomBackoffTime)
            yield env.process(self.sendpacket(gateway, packet))


def loranode_process(env: simpy.Environment, channel: simpy.Resource):
    global total_packets_created
    global lora_nodes_created

    global G
    global S
    global P_success
    global trx_attempts

    current_lnode = LoraNode(env, channel, lora_nodes_created)
    lora_nodes_created += 1
    while max(G) < 3.5 and lora_nodes_created <= 1000:
    # while True:
        # L is λ, the arrival rate in Poisson process
        # infrequent packet generation on Lora networks(0.05 packets per timeslot)
        L = 0.05
        # L = G[-1]
        P_arrival = L * np.exp(-L)
        # print("P arrival:", P_arrival)
        P_transmit = np.random.random()
        # print("P transmit:", P_transmit)
        if P_transmit <= P_arrival:
            pkt = Packet(total_packets_created)
            pkt.owner = current_lnode.id
            total_packets_created += 1

            yield env.process(current_lnode.sendpacket(l_gw, pkt))
            G.append(trx_attempts / ((env.now + 0.000001) / UPLINK_TIME))  # +0.000001 to avoid division by zero
            P_success = total_packets_sent / total_packets_created
            S.append(G[-1] * P_success)
            # print("G - traffic load:", G[-1])
            # print("S(G) - throughput:", S[-1])
            # print("loraNodes:", lora_nodes_created)
        else:
            yield wait_next_timeslot(env)


def wait_next_timeslot(env: simpy.Environment):
    if SLOTTED_ALOHA:
        # wait for the start of the next timeslot
        return env.timeout(TIMESLOT - (env.now % 1))
    else:
        # PURE ALOHA transmit immediately
        return env.timeout(0)


def setup(env: simpy.Environment):
    global G
    global lora_nodes_created

    # yield env.timeout(10)  # start at 10 to eliminate low env.now number bug at statistics calculation
    yield env.timeout(10)  # start at 10 to eliminate low env.now number bug at statistics calculation
    env.process(loranode_process(env, channel))
    while max(G) < 3.5 and lora_nodes_created <= 1000:
    # while True:
        # print("\n\n\n------====== Creating a new LoRa Node ======------\n\n\n")
        env.process(loranode_process(env, channel))
        yield env.timeout(10)


env = simpy.Environment()
channel = simpy.Resource(env, 1)
l_gw = LoraGateway(env)

env.process(setup(env))

env.run(until=MAX_TOTAL_TIMESLOTS)

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
print("Lora nodes:", lora_nodes_created)

print("Last G - traffic load:", G[-1])
print("MAX S(G) - throughput:", max(S))

if SLOTTED_ALOHA:
    plt.plot(G, S, 'r:')
    plt.title("Slotted LoRaWAN Protocol")
else:
    plt.plot(G, S, 'b:')
    plt.title("LoRaWAN Protocol")

plt.xlabel("G - traffic load")
plt.ylabel("S(G) - throughput")
plt.show()
