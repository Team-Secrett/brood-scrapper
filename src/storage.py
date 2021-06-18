import threading
import logging
import json

import zmq
from zmq.sugar import poll

from src.settings import (
    STORAGE_MCAST_ADDR
)
from src.utils.storage import Cache
from src.utils.udp import UDPSender
from src.utils.functions import random_id

logging.basicConfig(
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class Storage:
    """
    Represents a storage node in the system.
    Manage url caching
    """

    def __init__(self, ip, port, sport):
        self.address = (ip, port)
        self.ctx = zmq.Context()
        self.id = random_id()
        self.ping_sender = None
        self.router_sock = None

        self.cache = Cache()

    def init_ping_sender(self):
        self.ping_sender = UDPSender(
            's',
            self.id,
            self.address[1],
            self.address[0],
            STORAGE_MCAST_ADDR
        )
        threading.Thread(target=self.ping_sender.start, name='Ping-Workers').start()
        logging.info(f'Storage {self.id}: Ping service started...')

    def bind_router(self):
        self.router_sock = self.ctx.socket(zmq.ROUTER)
        self.router_sock.bind('tcp://%s:%s' % self.address)

    def start(self):
        """
        Start storage service
        """
        self.bind_router()
        self.init_ping_sender()

        poller = zmq.Poller()
        poller.register(self.router_sock, zmq.POLLIN | zmq.POLLOUT)

        logging.info(f'Storage {self.id}: Router service started...')
        print(self.address)
        while True:
            socks = dict(poller.poll())

            if self.router_sock in socks:
                try:
                    conn_id = self.router_sock.recv(zmq.DONTWAIT)
                    req = self.router_sock.recv_json(zmq.DONTWAIT)

                    logging.info(
                        f'Storage {self.id}: Processing incoming request...')

                    print('conn_id', conn_id)
                    print('req', req)

                    res = self._handle_request(req)

                    if res is not None:
                        print('Sending response:', res)
                        self.router_sock.send(conn_id, zmq.SNDMORE)
                        self.router_sock.send_json(res)
                except zmq.error.Again:
                    pass

    def _handle_request(self, req: dict):
        """
        request format:
            {
                "id": "client-id",
                "url": "www.example.com"
            } -> for fetch

            {
                "url": "www.example.com",
                "content": "<h1>html code for www.example.com</h1>"
            } -> for update

        response format (only for fetch's):
            {
                "id": "client-id",
                "url": "www.example.com",
                "hit": true,  // or false
                "content": "<h1>html code for www.example.com</h1>"
            }
        """

        if 'content' in req: # update request
            url, content = req['url'], req['content']

            self.cache.set(url, content)

            return None # empty response
        else: # fetch request
            url = req['url']

            content = self.cache.get(url)

            return {
                'id': req['id'],
                'url': url,
                'hit': content is not None,
                'content': content
            }
