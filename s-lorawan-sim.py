import simpy
from matplotlib.pylab import *
from numpy.random import RandomState

TIMESLOT = 1  # The timeslot duration
RX1_DELAY = 0.8
UPLINK_TIME = 0.9
ACK_TIME = 0.3

MAX_TOTAL_TIMESLOTS = 7200

RNG_SEED = 7589

total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0

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
    def __init__(self, env: simpy.Environment, id: int):
        self.env = env
        self.id = id

    def sendpacket(self, gateway: LoraGateway, packet: Packet):

        global total_packets_sent
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

        # check if there is only one transmit attempt at this slot
        with channel.request() as req:
            results = yield req | env.timeout(0.00000001)
            if req in results:
                yield env.timeout(UPLINK_TIME)
                yield env.process(gateway.receivepacket(packet))
                yield env.timeout(ACK_TIME)
                if packet.ACK:
                    print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", env.now)
                    total_packets_sent += 1
                    gateway.trx_attempts = 0
                else:
                    print('Collision!!!--n')
                    yield env.process(self.retransmitpacket(gateway, packet))
            else:
                print('Collision!!!--n')
                yield env.process(self.retransmitpacket(gateway, packet))

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        rbt = np.random.uniform(0, 10)
        print("( loraNode", self.id, ") Random Backoff Time:", rbt, "for Packet", packet.id)
        packet.re_trx_count += 1
        if packet.re_trx_count > 3:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            return
        else:
            yield env.timeout(rbt)
            yield env.process(self.sendpacket(gateway, packet))


def source(env: simpy.Environment, channel, prng=RandomState(0)):
    global total_packets_created
    global lora_nodes_created

    global G
    global S
    global P_success

    # Infinite loop for generating packets according to a poisson process.
    current_lnode = LoraNode(env, lora_nodes_created)
    lora_nodes_created += 1
    while True:
        # Generate next interarrival time
        arrivalrate = np.random.poisson(env.now)
        iat = prng.exponential(1.0 / (arrivalrate + 0.01))
        # iat = 1.0/(arrivalrate+0.00001)

        # This process will now yield to a 'timeout' event. This process will resume after iat time units.
        yield env.timeout(iat)

        pkt = Packet(total_packets_created)
        pkt.owner = current_lnode.id
        total_packets_created += 1

        yield env.process(current_lnode.sendpacket(l_gw, pkt))
        G.append(total_packets_created / (env.now / TIMESLOT))
        P_success = total_packets_sent / total_packets_created
        S.append(G[-1] * P_success)
        print("G - traffic load:", G[-1])
        print("S(G) - throughput:", S[-1])
        # print("loraNodes:", lora_nodes_created)


env = simpy.Environment()
channel = simpy.Resource(env, 1)
prng = RandomState(RNG_SEED)

l_gw = LoraGateway(env)

for _ in range(24):
    env.timeout(5)
    env.process(source(env, channel, prng))

# Run the simulation
env.run(until=MAX_TOTAL_TIMESLOTS)

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
print("Total timeslots:", MAX_TOTAL_TIMESLOTS)

print("G - traffic load:", total_packets_created / MAX_TOTAL_TIMESLOTS)
print("S(G) - throughput:", total_packets_sent / MAX_TOTAL_TIMESLOTS)

plot(G, S)
show()
