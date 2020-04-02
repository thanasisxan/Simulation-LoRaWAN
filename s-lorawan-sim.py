import simpy
import matplotlib.pyplot as plt
import numpy as np

TIMESLOT = 1  # The timeslot duration
RX1_DELAY = 0.82
UPLINK_TIME = 0.9
ACK_TIME = 0.2

# MAX_TOTAL_TIMESLOTS = 7200
MAX_TOTAL_TIMESLOTS = 402000


total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0
trx_attempts = 0

G = [0]  # Traffic load
S = [0]  # Throughput
P_success = 0  # chance of successfully transmitting a packet


class Packet:
    def __init__(self, num: int):
        self.ACK = False
        self.id = str(num)
        self.owner = None
        self.re_trx_count = 0


class LoraGateway:
    def __init__(self, env):
        self.env = env

    def receivepacket(self, packet: Packet):
        print("( loraGateway ) Received Packet", packet.id, "at", env.now)
        packet.ACK = True  # packet is acknowledged
        yield env.timeout(RX1_DELAY)
        print("( loraGateway ) Sending ACK for Packet", packet.id, "at:", env.now)


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
            # almost never happen
            if packet.re_trx_count == 0:
                print("( loraNode", self.id, ") The Packet", packet.id, "from ( loraNode", packet.owner,
                      ") arrived exactly at the start of a timeslot, transmitting at:", env.now)
        else:
            # The packet didn't arrive at the start of a timeslot as expected,
            # attempt to transmit at the start of the next timeslot...
            yield env.timeout(TIMESLOT - (env.now % 1))
            if packet.re_trx_count == 0:
                print("( loraNode", self.id, ") Attempt to transmit Packet", packet.id, "from ( loraNode", packet.owner,
                      ") at timeslot:", env.now)
            else:
                print("( loraNode", self.id, ") Retransmitting Packet", packet.id, "from ( loraNode",
                      packet.owner, ") at timeslot:", env.now)

        trx_attempts += 1
        req = channel.request()
        results = yield req | env.timeout(0)
        if req in results:
            yield env.timeout(UPLINK_TIME)
            yield env.process(gateway.receivepacket(packet))
            yield env.timeout(ACK_TIME)
            yield channel.release(req)
            # if packet.ACK:
            print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", env.now)
            total_packets_sent += 1
            gateway.trx_attempts = 0
            # else:
            #     print('Collision!!!--n')
            #     yield env.process(self.retransmitpacket(gateway, packet))
        else:
            print('Collision!!!--n')
            yield channel.release(req)
            yield env.process(self.retransmitpacket(gateway, packet))

        yield channel.release(req)

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        rbt = np.random.uniform(0, 15)
        print("( loraNode", self.id, ") Random Backoff Time:", rbt, "for Packet", packet.id)
        packet.re_trx_count += 1
        if packet.re_trx_count > 4:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            return
        else:
            yield env.timeout(rbt)
            yield env.process(self.sendpacket(gateway, packet))


def loranode_process(env: simpy.Environment, channel):
    global total_packets_created
    global lora_nodes_created

    global G
    global S
    global P_success

    current_lnode = LoraNode(env, channel, lora_nodes_created)
    lora_nodes_created += 1
    # while True:
    while max(G) < 3 and lora_nodes_created <= 1000:
        l = 0.1
        P_arrival = l * np.exp(-l)
        P_transmit = np.random.random()
        if P_transmit <= P_arrival:
            pkt = Packet(total_packets_created)
            pkt.owner = current_lnode.id
            total_packets_created += 1

            yield env.process(current_lnode.sendpacket(l_gw, pkt))
            # G.append(total_packets_created / (env.now / TIMESLOT))
            G.append(trx_attempts / (env.now + 0.000001))
            P_success = total_packets_sent / total_packets_created
            S.append(G[-1] * P_success)
            print("G - traffic load:", G[-1])
            print("S(G) - throughput:", S[-1])
            print("loraNodes:", lora_nodes_created)
            # yield env.timeout(env.now)
        else:
            yield env.timeout(TIMESLOT - (env.now % 1))


def setup(env):
    global G
    global lora_nodes_created
    env.process(loranode_process(env, channel))
    while max(G) < 3 and lora_nodes_created <= 1000:
        yield env.timeout(10)
        # print("\n\n\n------====== Creating a new LoRa Node!!! ======------\n\n\n")
        env.process(loranode_process(env, channel))


env = simpy.Environment()
channel = simpy.Resource(env, 1)
l_gw = LoraGateway(env)
env.process(setup(env))

env.run(until=MAX_TOTAL_TIMESLOTS)

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
print("Total timeslots:", MAX_TOTAL_TIMESLOTS)
print("Lora nodes:", lora_nodes_created)

print("G - traffic load:", total_packets_created / MAX_TOTAL_TIMESLOTS)
print("S(G) - throughput:", total_packets_sent / MAX_TOTAL_TIMESLOTS)

plt.plot(G, S)
plt.show()
