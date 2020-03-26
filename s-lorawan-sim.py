import simpy
from numpy.random import RandomState
import random
from collections import deque

channelBusy = False
timeSlot = 1  # The timeslot is only integer units of simulation time (no error accepted, like 1.01 at the moment)
rx1Delay = 0.2  # with this rxDelay the time of air is 2.2T as the paper suggest
# acceptableError = 0.11

ARR_RATE = 0.3
RNG_SEED = 25550

packets_created = 0
lora_nodes_created = 0
packets_sent = 0


class Packet:
    def __init__(self, id: int):
        self.ACK = False
        self.COL = False
        self.id = id


class LoraGateway(object):
    def __init__(self, env):
        self.env = env

    def receivepacket(self, packet: Packet):
        global channelBusy

        if channelBusy:
            packet.COL = True
            print("Collision!")
            channelBusy = False
        else:
            channelBusy = True
            # wait rx1 delay + timeslot
            # print("ChanelBusy:", channelBusy)
            print("( loraGateway ) Received Packet", packet.id, "at", self.env.now)
            packet.ACK = True  # packet is acknowledged
            # next timeslot to send ACK
            yield self.env.timeout(1 - (self.env.now % 1) + 1)
            print("( loraGateway ) Sending ACK for Packet", packet.id, "at next timeslot:", self.env.now)
            print("ChanelBusy:", channelBusy)
            channelBusy = False
        return


class LoraNode(object):
    def __init__(self, env: simpy.Environment, id: int):
        self.env = env
        self.id = id

    def sendpacket(self, gateway: LoraGateway, packet: Packet):
        global channelBusy
        global packets_sent
        print("( loraNode", self.id, ") Packet", packet.id, "created at", self.env.now)
        # wait send at next timeslot
        if self.env.now % 1 == 0:
            # almost never happen
            print("The packet arrived exactly at the start of a timeslot, transmitting immediately...")
        else:
            # The packet didn't arrive at the start of a timeslot as expected,
            # transmitting at the start of the next timeslot...
            yield self.env.timeout(1 - (self.env.now % 1))
            print("( loraNode", self.id, ") Transmitting Packet", packet.id, "at next timeslot:", self.env.now)

        # channelBusy = True
        print("ChanelBusy:", channelBusy)
        yield self.env.process(gateway.receivepacket(packet))
        yield self.env.timeout(rx1Delay)
        if packet.ACK:
            print("( loraNode", self.id, ") Received ACK for Packet", packet.id, "at:", self.env.now)
            packets_sent += 1
            channelBusy = False
        else:
            while not packet.ACK:
                # wait random backoff time and send at next avail timeslot
                channelBusy = True
                # print("ChanelBusy:", channelBusy)
                # random backoff time
                rbt = random.uniform(0, 10)
                print("( loraNode", self.id, ") Random Backoff Time:", rbt)
                yield self.env.timeout(rbt)
                # next timeslot
                yield self.env.timeout(1 - (self.env.now % 1))
                print("( loraNode", self.id, ") Retransmitting Packet", packet.id, "at:", self.env.now)
                yield self.env.process(gateway.receivepacket(packet))
            channelBusy = False

        return


def source(env: simpy.Environment, arr_rate, prng=RandomState(0)):
    """Source generates packets according to a simple Poisson process

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        arr_rate : float
            exponential arrival rate
        prng : RandomState object
            Seeded RandomState object for generating pseudo-random numbers.
            See https://docs.scipy.org/doc/numpy/reference/generated/numpy.random.RandomState.html

    """

    global packets_created
    global lora_nodes_created

    l_node = LoraNode(env, lora_nodes_created)

    lora_nodes_created += 1
    # Infinite loop for generatirng packets according to a poisson process.
    while True:
        # Generate next interarrival time
        iat = prng.exponential(1.0 / arr_rate)

        # This process will now yield to a 'timeout' event. This process will resume after iat time units.
        yield env.timeout(iat)

        pkt = Packet(packets_created)

        env.process(l_node.sendpacket(l_gw, pkt))

        # Update counter of patients
        packets_created += 1


# Initialize a simulation environment
env = simpy.Environment()
# Initialize a random number generator.
# See https://docs.scipy.org/doc/numpy/reference/generated/numpy.random.RandomState.html
prng = RandomState(RNG_SEED)

l_gw = LoraGateway(env)

runtime = 7200

for _ in range(100):
    env.process(source(env, ARR_RATE, prng))

# Run the simulation
env.run(until=runtime)
print("Packets created: ", packets_created)
print("Packets sent:", packets_sent)
print("Total timeslots:", runtime * lora_nodes_created)

print("Throughput:", packets_sent / (runtime * lora_nodes_created))
