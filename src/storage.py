import threading
import logging

import zmq

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

        res_queue = []

        while True:
            socks = dict(poller.poll())

            if self.router_sock in socks:
                if socks[self.router_sock] in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    conn_id = self.router_sock.recv(zmq.DONTWAIT)
                    req = self.router_sock.recv_json(zmq.DONTWAIT)
                    res_queue.append((conn_id, self._handle_request(req)))
                    logging.info(
                        f'Storage {self.id}: Processing incoming request...')

                if socks[self.router_sock] in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT):
                    try:
                        conn_id, res = res_queue.pop(0)
                    except IndexError:
                        pass
                    else:
                        if res is not None:
                            self.router_sock.send(conn_id, zmq.SNDMORE)
                            self.router_sock.send_json(res)
                            logging.info(f'Sended hit to {conn_id}: {res["url"]}')

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

            logging.info(f'Updated cache: {url}')
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
