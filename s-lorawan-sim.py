import simpy
from matplotlib.pylab import *
from numpy.random import RandomState

TIMESLOT = 1  # The timeslot is only integer units of simulation time (no error accepted, like 1.01 at the moment)
RX1_DELAY = 0.85
UPLINK_TIME = 1
ACK_TIME = 0.37

MAX_TOTAL_TIMESLOTS = 7200

ARR_RATE = 0.4
RNG_SEED = 65533

total_packets_created = 0
lora_nodes_created = 0
total_packets_sent = 0
trx_attempts_ts = 0  # number of transmission attempts in current timeslot

G = [0]  # Traffic load
S = [0]  # Throughput
P_success = 0  # chance of successfully transmitting a packet


class Packet:
    def __init__(self, num: int):
        self.ACK = False
        self.id = str(num)
        self.owner = None
        self.re_trx_count = 0


class LoraGateway(object):
    def __init__(self, env):
        self.env = env
        self.trx_attempts = 0

    def receivepacket(self, packet: Packet):
        self.trx_attempts += 1
        if self.trx_attempts == 1:
            print("( loraGateway ) Received Packet", packet.id, "at", env.now)
            packet.ACK = True  # packet is acknowledged
            self.trx_attempts += 1
            # next timeslot to send ACK
            yield env.timeout(RX1_DELAY)
            print("( loraGateway ) Sending ACK for Packet", packet.id, "at:", env.now)
        else:
            print("Collision!!!--gw")


class LoraNode(object):
    def __init__(self, env: simpy.Environment, id: int):
        self.env = env
        self.id = id

    def work(self):
        global total_packets_created
        arrivalrate = np.random.poisson(env.now)
        iat = prng.exponential(1.0 / (arrivalrate + 0.001))

        # This process will now yield to a 'timeout' event. This process will resume after iat time units.
        yield env.timeout(iat)

        pkt = Packet(total_packets_created)
        pkt.owner = self.id
        total_packets_created += 1

        env.process(self.sendpacket(l_gw, pkt))

    def sendpacket(self, gateway: LoraGateway, packet: Packet):

        global total_packets_sent
        global trx_attempts_ts
        if packet.re_trx_count == 0:
            print("( loraNode", self.id, ") Packet", packet.id, "created at:", env.now, "from ( loraNode", packet.owner,
                  ")")
        # else:
        #     print("( loraNode", self.id, ") Retransmitting Packet", packet.id, "from ( loraNode",
        #           packet.owner, ")")
        # wait send at next timeslot
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

        trx_attempts_ts += 1

        # check if there is only one transmit attempt at this slot
        if trx_attempts_ts == 1:
            yield env.timeout(UPLINK_TIME)
            yield env.process(gateway.receivepacket(packet))
            yield env.timeout(ACK_TIME)
            if packet.ACK:
                print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", env.now)
                total_packets_sent += 1
                trx_attempts_ts = 0
                gateway.trx_attempts = 0
            else:
                print('Collision!!!--n')
                print("trx_attempts_ts:", trx_attempts_ts)
                trx_attempts_ts = 0
                yield env.process(self.retransmitpacket(gateway, packet))
        else:
            print('Collision!!!--n')
            print("trx_attempts_ts:", trx_attempts_ts)
            yield env.process(self.retransmitpacket(gateway, packet))

        # self.work()

    def retransmitpacket(self, gateway: LoraGateway, packet: Packet):
        global trx_attempts_ts
        rbt = np.random.uniform(0, 10)
        print("( loraNode", self.id, ") Random Backoff Time:", rbt, "for Packet", packet.id)
        # trx_attempts_ts = 0
        packet.re_trx_count += 1
        if packet.re_trx_count > 2:
            print("Maximum retransmissions for Packet", packet.id, "from ( loraNode", packet.owner, " )")
            return
        else:
            yield env.timeout(rbt)
            # next timeslot
            # yield env.timeout(TIMESLOT - (self.env.now % 1))
            yield env.process(self.sendpacket(gateway, packet))


def source(env: simpy.Environment, arr_rate, prng=RandomState(0)):
    global total_packets_created
    global lora_nodes_created
    global trx_attempts_ts

    global G
    global S
    global P_success

    # while max(G) < 10 and lora_nodes_created <= 1000:
    #     current_lnode = LoraNode(env, lora_nodes_created)
    #
    #     lora_nodes_created += 1
    #     yield env.process(current_lnode.work())
    #     if env.now != 0:  # avoid division by zero
    #         G.append(total_packets_created / (env.now / TIMESLOT))
    #         P_success = total_packets_sent / total_packets_created
    #         S.append(G[-1] * P_success)
    #         print("G - traffic load:", G[-1])
    #         print("S(G) - throughput:", S[-1])
    #         print("loraNodes:", lora_nodes_created)

    # Infinite loop for generating packets according to a poisson process.
    current_lnode = LoraNode(env, lora_nodes_created)
    lora_nodes_created += 1
    while True:
        # Generate next interarrival time
        # iat = prng.exponential(1.0 / arr_rate)
        arrivalrate = np.random.poisson(env.now)
        iat = prng.exponential(1.0 / (arrivalrate + 0.01))

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
        print("loraNodes:", lora_nodes_created)
    #     # trx_attempts_ts = 0


# Initialize a simulation environment
env = simpy.Environment()
# Initialize a random number generator.
# See https://docs.scipy.org/doc/numpy/reference/generated/numpy.random.RandomState.html
prng = RandomState(RNG_SEED)

l_gw = LoraGateway(env)

for _ in range(124):
    env.process(source(env, ARR_RATE, prng))

# env.process(source(env, ARR_RATE, prng))

# while G < 2 and lora_nodes_created <= 1000:
#     env.process(source(env, ARR_RATE, prng))
#     if env.now != 0:  # avoid division by zero
#         G = total_packets_created / (env.now / TIMESLOT)
#         P_success = total_packets_sent / total_packets_created
#         S = G * P_success


# Run the simulation
env.run(until=MAX_TOTAL_TIMESLOTS)
# env.run()

print("Packets created: ", total_packets_created)
print("Packets sent:", total_packets_sent)
print("Total timeslots:", MAX_TOTAL_TIMESLOTS)

print("G - traffic load:", total_packets_created / MAX_TOTAL_TIMESLOTS)
print("S(G) - throughput:", total_packets_sent / MAX_TOTAL_TIMESLOTS)

plot(G, S)
show()
