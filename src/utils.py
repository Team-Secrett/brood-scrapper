from __future__ import annotations
from typing import Tuple, Dict
import uuid
import time
import string
import random

import zmq

try:
    from src import settings
except ImportError:
    import settings


def pipe(ctx: zmq.Context) -> Tuple[zmq.Socket, zmq.Socket]:
    """
    Return a pipe between two sockets for inproc comunication.
    """
    p0 = ctx.socket(zmq.PAIR)
    p1 = ctx.socket(zmq.PAIR)
    url = 'inproc://%s' % uuid.uuid1()

    p0.bind(url)
    p1.connect(url)

    return p0, p1


def random_id(length=4):
    """
    Generate a case sensitive random string.
    """
    symbols = string.ascii_letters + string.digits
    return ''.join(random.choice(symbols) for _ in range(length))


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

class Timestamp:
    """
    Vector clock timestamp used in messages.
    """

    def __init__(self, timestamp: Dict[str, int] = {}):
        self.timestamp = timestamp

    def __getitem__(self, key):
        return self.timestamp[key]

    def __setitem__(self, key, item):
        self.timestamp[key] = item

    def __iter__(self):
        for k in self.timestamp:
            yield k

    def __lt__(self, other: Timestamp):
        one_less = False    # at least one component less strict

        for k in other:
            try:
                if self[k] > other[k]:
                    return False

                if not one_less and self[k] < other[k]:
                    one_less = True
            except KeyError:
                continue

        return one_less

    def __add__(self, other: Timestamp):
        """
        Merge two timestamp histories.
        Older timestamp should be the left value.
        """
        return Timestamp({**self.timestamp, **other.timestamp})

    def __str__(self):
        return f'ts<{", ".join(f"({self[k]}, {k})" for k in self)}>'

    def __repr__(self):
        return self.__str__()

    def update(self, id_):
        """
        Register the ocurrence of an event in id_.
        Increase the clock by 1.
        """
        try:
            self[id_] += 1
        except KeyError:
            self[id_] = 1

    @staticmethod
    def test():
        t1 = Timestamp({'a': 1, 'b': 2, 'c': 3})
        t2 = Timestamp({'a': 0, 'b': 4, 'c': 2})
        t3 = Timestamp({'a': 0, 'b': 1, 'c': 2})
        t4 = Timestamp({'d': 10, 'c': 10})
        t5 = Timestamp({'e': 5, 'f': 4})

        assert not t1 < t1
        assert not t1 < t2
        assert not t2 < t1
        assert not t1 < t3
        assert t3 < t1
        t6 = t4 + t5
        print(t4)
        print(t5)
        print(t6)


if __name__ == '__main__':
    Timestamp.test()
