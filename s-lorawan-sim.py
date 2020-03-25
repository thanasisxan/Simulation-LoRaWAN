import simpy


print(simpy.__version__)


channelBusy=False

class Packet:
    def __init__(self):
        self.ACK=False
        self.COL=False

class Gateway:
    def __init__(self):
        super().__init__()
        
    def receivePacket(self, packet):
        global channelBusy
        
        if(channelBusy):
            packet.COL=True
        else:
            channelBusy=True
            # wait rx1 delay+timeslot
            packet.ACK=True #packet is aknowledged
        
        return packet
    
class endNode:
    def __init__(self):
        super().__init__()
        
    def sendPacket(self, gateway, packet):
        global channelBusy
        packet = gateway.receivePacket(packet)
        if(packet.ACK):
            #wait 1 timeslot
            channelBusy=False