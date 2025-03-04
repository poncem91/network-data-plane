'''
Created on Oct 12, 2016

@author: mwittie
'''
import queue
import threading
from rprint import print


## wrapper class for a queue of packets
class Interface:
    ## @param max_queue_size - the maximum size of the queue storing packets
    #  @param mtu - the maximum transmission unit on this interface
    def __init__(self, max_queue_size=0):
        self.mtu = None
        self.queue = queue.Queue(max_queue_size)

    ## get packet from the queue interface
    def get(self):
        try:
            return self.queue.get(False)
        except queue.Empty:
            return None

    ## put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, block=False):
        self.queue.put(pkt, block)


## Implements a network layer packet
class NetworkPacket:
    ## packet encoding lengths
    dst_addr_S_length = 2
    pkt_id_S_length = 3
    frag_flag_S_length = 1
    frag_offset_S_length = 3
    header_length = dst_addr_S_length + pkt_id_S_length + frag_flag_S_length + frag_offset_S_length

    ##@param dst_addr: address of the destination host
    # @param data_S: packet payload
    def __init__(self, dst_addr, data_S, pkt_id, frag_flag=0, frag_offset=0):
        self.dst_addr = dst_addr
        self.data_S = data_S
        self.pkt_id = pkt_id
        self.frag_flag = frag_flag
        self.frag_offset = frag_offset

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        byte_S += str(self.pkt_id).zfill(self.pkt_id_S_length)
        byte_S += str(self.frag_flag).zfill(self.frag_flag_S_length)
        byte_S += str(self.frag_offset).zfill(self.frag_offset_S_length)
        byte_S += self.data_S
        return byte_S

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst_addr = int(byte_S[0: NetworkPacket.dst_addr_S_length])
        pkt_id = byte_S[
                 NetworkPacket.dst_addr_S_length:(NetworkPacket.dst_addr_S_length + NetworkPacket.pkt_id_S_length)]
        frag_flag = byte_S[(NetworkPacket.dst_addr_S_length + NetworkPacket.pkt_id_S_length):(NetworkPacket.dst_addr_S_length + NetworkPacket.pkt_id_S_length + NetworkPacket.frag_flag_S_length)]
        frag_offset = byte_S[(NetworkPacket.dst_addr_S_length + NetworkPacket.pkt_id_S_length + NetworkPacket.frag_flag_S_length):NetworkPacket.header_length]
        data_S = byte_S[NetworkPacket.header_length:]
        return self(dst_addr, data_S, pkt_id, frag_flag, frag_offset)


## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    # @param mtu: MTU for all interfaces
    def __init__(self, addr):
        self.addr = addr
        self.id_count = 0
        self.in_intf_L = [Interface()]
        self.out_intf_L = [Interface()]
        self.stop = False  # for thread termination
        self.frag_pkt_buffer = {}

    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)

    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        # splits up packet into two pieces to be able to forward them through the host's out interface
        packet_len = len(data_S) // 2
        pkt_id = str(self.addr) + str(self.id_count)
        p = NetworkPacket(dst_addr, data_S[:packet_len], pkt_id)
        print('%s: sending packet "%s" on the out interface with mtu=%d' % (self, p, self.out_intf_L[0].mtu))
        self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully
        self.id_count += 1
        pkt_id = str(self.addr) + str(self.id_count)
        p = NetworkPacket(dst_addr, data_S[packet_len:], pkt_id)
        print('%s: sending packet "%s" on the out interface with mtu=%d' % (self, p, self.out_intf_L[0].mtu))
        self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully

    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.in_intf_L[0].get()
        # if there's an incoming packet start building up fragmented packets into a buffer until all fragments have
        # been received, then print packet that and clear said buffer
        if pkt_S is not None:
            frag_pkt = NetworkPacket.from_byte_S(pkt_S)
            pkt_id = int(frag_pkt.pkt_id)
            if pkt_id in self.frag_pkt_buffer.keys():
                self.frag_pkt_buffer[pkt_id].append(frag_pkt.data_S)
            else:
                self.frag_pkt_buffer[pkt_id] = [frag_pkt.data_S]
            if frag_pkt.frag_flag == "0":
                frag_list = self.frag_pkt_buffer[pkt_id]
                del self.frag_pkt_buffer[pkt_id]
                print('%s: received packet "%s" on the in interface' % (self, ''.join(frag_list)))

    ## thread target for the host to keep receiving data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            # receive data arriving to the in interface
            self.udt_receive()
            # terminate
            if (self.stop):
                print(threading.currentThread().getName() + ': Ending')
                return


## Implements a multi-interface router described in class
class Router:

    ##@param name: friendly router name for debugging
    # @param intf_count: the number of input and output interfaces
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_count, max_queue_size):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    ## look through the content of incoming interfaces and forward to
    # appropriate outgoing interfaces
    def forward(self):
        for i in range(len(self.in_intf_L)):
            pkt_S = None
            try:
                # get packet from interface i
                pkt_S = self.in_intf_L[i].get()
                # if packet exists make a forwarding decision
                if pkt_S is not None:
                    p = NetworkPacket.from_byte_S(pkt_S)  # parse a packet out
                    # calculate max load of data interface can handle
                    max_load = self.out_intf_L[i].mtu - NetworkPacket.header_length
                    frag_flag = 1
                    frag_offset = 0
                    buffer = p.data_S

                    # iterates over buffer sending packet fragments until end of packet
                    while len(buffer) > 0:
                        if len(buffer) <= max_load:  # checks if last fragment in packet
                            frag_flag = 0
                        # creates fragment packet and forwards fragment
                        frag_pkt = NetworkPacket(p.dst_addr, buffer[:max_load], p.pkt_id, frag_flag, frag_offset)
                        print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' \
                              % (self, frag_pkt, i, i, self.out_intf_L[i].mtu))
                        self.out_intf_L[i].put(frag_pkt.to_byte_S())

                        buffer = buffer[max_load:]
                        frag_offset += len(buffer[:max_load])

            except queue.Full:
                print('%s: packet "%s" lost on interface %d' % (self, p, i))
                pass

    ## thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.forward()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return
