"""
Types for worker node.
"""
from __future__ import annotations
from typing import Optional, Dict, Tuple
from collections import OrderedDict
import logging
import threading
import time

import zmq
import requests
from requests import Response

from src import settings
from src.utils.common import DiscoveringInterface, Peer


logging.basicConfig(
    # format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class StorageDisc(DiscoveringInterface):

    def __init__(self, inter_ip: str, pipe: zmq.Socket):
        super().__init__(
            inter_ip,
            settings.STORAGE_MCAST_ADDR,
            settings.STORAGE_PING_SIZE,
            pipe
        )

    def handle_beacon(self, fd, event):
        data, addr = self.udp.recv()
        flag, sid, sport = data
        addr = (addr[0], int(sport))

        if flag != 's':
            return

        if sid in self.peers:
            self.peers[sid].is_alive()

            if self.peers[sid].addr != addr:
                self.peers[sid].update(addr)
                self.pipe_sock.send_json(
                    {
                        'action': 'update',
                        'peer': sid,
                        'addr': addr,
                    }
                )
        else:
            self.peers[sid] = Peer(sid, (addr[0], int(sport)))
            self.pipe_sock.send_json(
                {
                    'action': 'add',
                    'peer': sid,
                    'addr': [addr[0], int(sport)],
                }
            )


class Request:
    """
    Class that represents a request handled by a worker.
    """

    hit: bool = None
    content: str = None
    expiry: int = None
    client_conn: bytes = None

    def __init__(self, conn: bytes):
        self.client_conn = conn

    def start_timer(self):
        """
        Set expiry time for a request to cache.
        """
        self.expiry = time.time() + settings.WORKER_REQ_EXPIRY

    def is_hit(self, hit: bool):
        """
        Mark request as hitted or not in cache.
        """
        self.hit = hit

    @property
    def is_expired(self) -> bool:
        """
        Timed out the response from cache.
        """
        if self.expiry is not None and self.expiry < time.time():
            self.hit = False
            return True

        return False

    def __eq__(self, other: Request):
        return self.cid == other.cid and self.url == other.url

    def hash(self):
        return hash(self.cid + self.url)


class RequestsMonitor:
    """
    Class for keeping track of received requests from clients.
    """
    RequestsDict = Dict[Tuple[str, str], Request]

    lock = threading.Lock()
    new: RequestsDict = OrderedDict()           # new requests to be processed
    caching: RequestsDict = OrderedDict()       # requests passed to cache
    scrapping: RequestsDict = OrderedDict()     # rqueests didn't hit
    ready: RequestsDict = OrderedDict()         # requests ready with content

    def prune_caching(self):
        """
        This method should be invoked in a single thread.
        Pop expired requests in caching adn put it to scrapping queue.
        """
        while True:
            with self.lock:
                for id_url in list(self.caching):
                    if self.caching[id_url].is_expired:
                        req_expired = self.caching.pop(id_url)
                        req_expired.is_hit(False)
                        self.scrapping[id_url] = req_expired
                        logging.info(f'Timed out cache response for {id_url[1]}')

            time.sleep(0.25)

    def _first(self, dict_: OrderedDict, popit: bool) -> Tuple[Tuple[str, str], Request]:
        """
        Return first item in an ordered dict.
        """
        try:
            id_url, req = next(iter(dict_.items()))
        except StopIteration:
            return None, None

        if popit:
            dict_.pop(id_url)

        return id_url, req

    def new_next(self) -> Optional[Tuple[str, str]]:
        """
        Pop and return next request ready to be checked in cache.
        Request is queued in caching queue.
        """
        with self.lock:
            id_url, req = self._first(self.new, True)
            if id_url is not None and req is not None:
                req.start_timer()
                self.caching[id_url] = req
                return id_url
            else:
                return None

    def scrapping_next(self) -> Optional[Tuple[str, str]]:
        """
        Return next request ready to be scrapped.
        """
        with self.lock:
            id_url, req = self._first(self.scrapping, False)
            return id_url

    def ready_next(self) -> Tuple[Tuple[str, str], Request]:
        """
        Pop and return next request ready to be delivered to client.
        """
        with self.lock:
            id_url, req = self._first(self.ready, True)
            return id_url, req

    def add_new(self, id_url: Tuple[str, str], conn: bytes):
        """
        Add a new request to be processed.
        """
        with self.lock:
            self.new[id_url] = Request(conn)

    def move_new_to_scrapping(self):
        """
        Move a request from new queue to scrapping queue, this should
        be done if no cache servers are detected.
        """
        with self.lock:
            id_url, req = self._first(self.new, True)
            if id_url is not None and req is not None:
                req.is_hit(False)
                self.scrapping[id_url] = req

    def move_caching_to_scrapping(self, id_url: Tuple[str, str]):
        """
        Move request to scrapping queue as a consequence it didn't
        hitted cache.
        """
        with self.lock:
            req = self.caching.pop(id_url)
            req.is_hit(False)
            self.scrapping[id_url] = req

    def move_caching_to_ready(self, id_url: Tuple[str, str], content: str):
        """
        Move request from caching queue to ready queue as
        consequence it was a hit.
        """
        with self.lock:
            req = self.caching.pop(id_url)
            req.is_hit(True)
            req.content = content
            self.ready[id_url] = req

    def move_scrapping_to_ready(self, id_url: Tuple[str, str], content: str):
        """
        Move a request from scrapping queue to ready queue after it
        was succesfuly scrapped.
        """
        with self.lock:
            req = self.scrapping.pop(id_url)
            req.content = content
            self.ready[id_url] = req
            # print(req.content[:20])
            # print(len(self.ready))


class Scrapper:

    @staticmethod
    def _get(url: str, params: dict = {}, timeout: float = None) -> Response:
        return requests.get(url, params, timeout=timeout).content.decode('utf8')

    @staticmethod
    def start_scrapper(monitor: RequestsMonitor):
        """
        Start scrapper that process requests from scrapping queue.
        """
        while True:
            id_url = monitor.scrapping_next()
            if id_url is not None:
                content = Scrapper._get('http://' + id_url[1])
                monitor.move_scrapping_to_ready(id_url, content)
                logging.info(
                    f'Scrapped {id_url[1]}, content length: {len(content)}')
