import simpy

print(simpy.__version__)

channelBusy = False


class Packet:
    def __init__(self):
        self.ACK = False
        self.COL = False


class Gateway:
    def __init__(self):
        super().__init__()

    def receivePacket(self, packet):
        global channelBusy

        if (channelBusy):
            packet.COL = True
        else:
            channelBusy = True
            # wait rx1 delay+timeslot
            packet.ACK = True  # packet is aknowledged

        return packet


class EndNode:
    def __init__(self):
        super().__init__()

    def sendPacket(self, gateway, packet):
        global channelBusy
        # wait send at next timeslot
        packet = gateway.receivePacket(packet)
        if (packet.ACK):
            channelBusy = False
