"""
UDP multicast groups comunication interfaces.
"""
from typing import List, Tuple
import struct
import socket
import time


class UDPReceiver:
    """
    Class for receive beacons in a multicast groups.
    """

    def __init__(self, inter_ip, mcast_addr, beacon_size):
        self.inter_ip = inter_ip    # interface where listen for udp packets
        self.mcast_addr = mcast_addr
        self.beacon_size = beacon_size
        self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        self.sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(self.mcast_addr)
        mreq = struct.pack(
            '4s4s',
            socket.inet_aton(self.mcast_addr[0]),
            socket.inet_aton(self.inter_ip)
        )
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def recv(self) -> Tuple[List[str], Tuple[str, int]]:
        data, addr = self.sock.recvfrom(self.beacon_size)
        data = data.decode('utf8').split(' ')

        return data, addr


class UDPSender:
    """
    Class for send beacons in a multicast group.
    """

    def __init__(self, flag, id, port, inter_ip, mcast_addr):
        self.flag = flag
        self.id = id
        self.port = port
        self.inter_ip = inter_ip
        self.mcast_addr = mcast_addr

    def start(self, interval=1):
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        while True:
            sock.sendto(
                f'{self.flag} {self.id} {self.port}'.encode('utf8'),
                self.mcast_addr
            )
            time.sleep(interval)
