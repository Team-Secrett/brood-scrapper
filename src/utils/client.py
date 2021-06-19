"""
Types for client nodes.
"""
from typing import Optional, List, Tuple
import time

import zmq

from src import settings
from src.utils.common import DiscoveringInterface, Peer


class WorkerDisc(DiscoveringInterface):

    def __init__(self, inter_ip, pipe: zmq.Socket):
        super().__init__(
            inter_ip,
            settings.WORKER_MCAST_ADDR,
            settings.WORKER_PING_SIZE,
            pipe
        )

    def handle_beacon(self, fd, event):
        data, addr = self.udp.recv()
        flag, wid, wport = data
        addr = (addr[0], int(wport))

        # print('new beacon:', data)

        if flag != 'w':
            return

        if wid in self.peers:
            self.peers[wid].is_alive()

            if self.peers[wid].addr != addr:
                print(self.peers[wid].addr, ':-->', addr)
                self.peers[wid].update(addr)
                self.pipe_sock.send_json(
                    {
                        'action': 'update',
                        'peer': wid,
                        'addr': addr,
                    }
                )
        else:
            self.peers[wid] = Peer(wid, (addr[0], int(wport)))
            self.pipe_sock.send_json(
                {
                    'action': 'add',
                    'peer': wid,
                    'addr': [addr[0], int(wport)],
                }
            )


class UrlFeeder:

    def __init__(self, fp: str, n: int, timeout: int = 30):
        self.buffer: List[Tuple[str, int]] = []
        self.pendant: List[Tuple[str, int]] = []
        self.timeout = timeout

        with open(fp, encoding='utf8') as f:
            c = 0
            for line in f:
                if not line.startswith('#'):
                    self.buffer.append((line[:-1], 0))
                    c += 1
                    if c == n:
                        break

    def append(self, url: str, depth: int = 0):
        """
        Add url to buffer
        """
        self.buffer.append((url, depth))

    def find_pending(self, url: str) -> Optional[List[Tuple[str, int]]]:
        for i in self.buffer:
            if i[0] == url:
                return i
        return None

    def feed(self) -> Optional[str]:
        """
        Return an url from buffer and keep track of pendant urls.
        """
        # move expired url to buffer
        now = time.time()
        for p in list(self.pendant):
            if p[1] < now:
                self.buffer.append(p[0])
                self.pendant.remove(p)

        # return to client an url
        try:
            self.pendant.append(
                (url := self.buffer.pop(0), time.time() + self.timeout))
            return url
        except IndexError:  # buffer is empty
            return None

    def done(self, url: str) -> Optional[Tuple[str, int]]:
        """
        Confirmation that url has been scrapped. If url exists then return item
        """
        for p in list(self.pendant):
            if p[0] == url:
                ret = p
                self.pendant.remove(p)
                return ret
        return None

    def __len__(self):
        return len(self.buffer) + len(self.pendant)

    def __bool__(self):
        return self.__len__() > 0
