"""
Common types for nodes.
"""
from __future__ import annotations
from typing import Tuple, Dict
import time

import zmq
from tornado.ioloop import IOLoop, PeriodicCallback

from src import settings
from src.utils.udp import UDPReceiver


class Peer:

    def __init__(self, uuid, addr: Tuple[str, int]):
        self.uuid = uuid
        self.addr = addr
        self.expires_at = None
        self.is_alive()

    def is_alive(self):
        """
        Reset the peers expiry time.
        Call this method whenever we get any activity from a peer.
        """
        self.expires_at = time.time() + settings.PEER_EXPIRY

    def update(self, new_addr):
        self.addr = new_addr

    def __eq__(self, other: Peer):
        return self.uuid == other.uuid

    def __hash__(self):
        return hash(self.uuid)

    def __str__(self):
        return f'({self.uuid}::{self.addr}, {self.expires_at})'

    def __repr__(self):
        return f'Peer{self.__str__()}'


class DiscoveringInterface:

    def __init__(self, inter_ip: str, mcast_addr: str, beacon_size: int, pipe: zmq.Socket):
        self.pipe_sock = pipe
        self.loop = None
        self.udp = UDPReceiver(inter_ip, mcast_addr, beacon_size)
        self.peers: Dict[str, Peer] = {}

    def stop(self):
        self.pipe.close()
        self.loop.stop()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def start(self):
        self.loop = IOLoop()
        self.loop.add_handler(
            self.udp.sock.fileno(), self.handle_beacon, IOLoop.READ)

        reaper = PeriodicCallback(self.reap_peers, 1000)
        reaper.start()

        self.loop.start()

    def reap_peers(self):
        now = time.time()
        for p in dict(self.peers):
            peer = self.peers[p]
            if peer.expires_at < now:
                self.peers.pop(peer.uuid)
                self.pipe_sock.send_json(
                    {
                        'action': 'delete',
                        'peer': peer.uuid,
                    }
                )

    def handle_beacon(self, fd, event):
        raise NotImplementedError()
