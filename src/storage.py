import threading
import logging

import zmq

from src.settings import (
    STORAGE_MCAST_ADDR
)
from src.utils.storage import Cache
from src.utils.worker import StorageDisc
from src.utils.udp import UDPSender
from src.utils.functions import random_id, pipe

logging.basicConfig(
    # format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class Storage:
    """
    Represents a storage node in the system.
    Manage url caching
    """

    def __init__(self, ip, port, cache_folder, update):
        self.address = (ip, port)
        self.ctx = zmq.Context()
        self.id = random_id()
        self.ping_sender = None
        self.router_sock = None

        self.discoverer = None          # discovering service
        self.disc_sock = None           # PAIR sock to pipe discovering service
        self.updates_in_sock = None     # DEALER sock to listen updates
        self.updates_out_sock = None    # ROUTER sock for send updates
        self.storages = {}              # storages discovered
        self.storage_conns = {}

        self.cache = Cache(cache_folder)

        self.res_queue = []     # responses to deliver
        self.upd_queue = []     # updates to deliver

        self.update_cache = update     # storage should update his cache

    def init_ping_sender(self):
        self.ping_sender = UDPSender(
            's',
            self.id,
            self.address[1],
            self.address[0],
            STORAGE_MCAST_ADDR
        )
        threading.Thread(
            target=self.ping_sender.start,
            name='Ping-Workers',
            daemon=True
        ).start()
        logging.info(f'Storage {self.id}: Ping service started...')

    def init_discovering_service(self):
        self.disc_sock, pipe_sock = pipe(self.ctx)
        self.discoverer = StorageDisc(self.address[0], pipe_sock)
        threading.Thread(
            target=self.discoverer.start,
            name='Discoverer',
            daemon=True
        ).start()
        logging.info('Storage discovering service started...')

        updates_address = (self.address[0], self.address[1] + 1)
        self.updates_in_sock = self.ctx.socket(zmq.DEALER)
        self.updates_out_sock = self.ctx.socket(zmq.ROUTER)
        self.updates_out_sock.bind('tcp://%s:%d' % updates_address)
        logging.info(f'Sockets for updates binded: {updates_address}')

    def bind_router(self):
        self.router_sock = self.ctx.socket(zmq.ROUTER)
        self.router_sock.bind('tcp://%s:%s' % self.address)

    def start(self):
        """
        Start storage service
        """
        self.bind_router()
        self.init_discovering_service()
        self.init_ping_sender()

        poller = zmq.Poller()
        poller.register(self.disc_sock, zmq.POLLIN)
        poller.register(self.updates_in_sock, zmq.POLLIN | zmq.POLLOUT)
        poller.register(self.updates_out_sock, zmq.POLLIN | zmq.POLLOUT)
        poller.register(self.router_sock, zmq.POLLIN | zmq.POLLOUT)

        logging.info(f'Storage {self.id}: Router service started...')

        while True:
            socks = dict(poller.poll())

            # ========================================

            # TODO: refresh self.storage_conns

            if self.disc_sock in socks:
                msg = self.disc_sock.recv_json(zmq.DONTWAIT)

                # get action, storage id and addr (if present)
                action = msg['action']
                sid = msg['peer']
                try:
                    addr = (msg.get('addr')[0], msg.get('addr')[1] + 1)
                except TypeError:
                    if action in ('add', 'update'):
                        logging.warning(f'Storage {sid}: update without address')
                        continue

                if (self.address[0], self.address[1] + 1) == addr:
                    continue

                # storage is not longer accessible, close the connection
                if action == 'delete':
                    self.updates_in_sock.disconnect('tcp://%s:%d' % self.storages[sid])
                    self.storages.pop(sid)
                    try:
                        self.storage_conns.pop(sid)
                    except KeyError:
                        pass
                    logging.info(f'Removed storage {sid}')

                # new worker, establish a connection
                elif action == 'add':
                    self.updates_in_sock.connect('tcp://%s:%d' % addr)
                    self.storages[sid] = addr
                    logging.info(f'Added storage {sid}: {addr}')

                # worker changed his interface, update the conection
                elif action == 'update':  # TODO: breaking with 2+ storages
                    self.updates_in_sock.disconnect('tcp://%s:%d' % self.storages[sid])
                    self.updates_in_sock.connect('tcp://%s:%d' % addr)
                    old_addr, self.storages[sid] = self.storages[sid], addr
                    logging.info(f'Updated storage {sid}: {old_addr} -> {addr}')

            # ========================================

            # DEALER sock for receive updates and request/receive full updates
            if self.updates_in_sock in socks:
                # handle update
                if socks[self.updates_in_sock] in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    data = self.updates_in_sock.recv_json(zmq.DONTWAIT)
                    self._handle_request(data)

                # if this node is new should request a full update
                if socks[self.updates_in_sock] in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT):
                    if self.update_cache:
                        logging.info('Requesting full update...')
                        self.updates_in_sock.send_json(
                            {
                                'id': self.id,
                                'new': True,
                                'updateme': True,
                            }
                        )
                        # try:
                        res = self.updates_in_sock.recv_json()
                        # except zmq.error.Again:
                            # pass
                        # else:
                        while res['url'] is not None and res['content'] is not None:
                            self._handle_request(res)
                            res = self.updates_in_sock.recv_json()
                        logging.info('Full update completed')

                        self.update_cache = False
                    else:
                        self.updates_in_sock.send_json(
                            {
                                'id': self.id,
                                'new': True,
                                'updateme': False
                            }
                        )

            # ========================================

            # ROUTER sock for broadcast updates and send full updates
            if self.updates_out_sock in socks:
                if socks[self.updates_out_sock] in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT):
                    try:
                        url, content = self.upd_queue.pop(0)
                    except IndexError:
                        pass
                    else:
                        c = 0
                        for conn_id in self.storage_conns.values():
                            self.updates_out_sock.send(conn_id, zmq.SNDMORE)
                            self.updates_out_sock.send_json(
                                {
                                    'url': url,
                                    'content': content,
                                    'spread': False,
                                }
                            )
                            c += 1
                        logging.info(f'Updated {c} storages: {url}')

                # receive a full update request from new storage
                if socks[self.updates_out_sock] in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    conn_id = self.updates_out_sock.recv()
                    data = self.updates_out_sock.recv_json()
                    if data['new']:
                        self.storage_conns[data['id']] = conn_id
                        if data['updateme']:
                            for url, content in self.cache:
                                self.updates_out_sock.send(conn_id, zmq.SNDMORE)
                                self.updates_out_sock.send_json(
                                    {
                                        'url': url,
                                        'content': content,
                                        'spread': False,
                                    }
                                )
                            # send empty update as end flag
                            self.updates_out_sock.send(conn_id, zmq.SNDMORE)
                            self.updates_out_sock.send_json(
                                {
                                    'url': None,
                                    'content': None,
                                    'spread': False,
                                }
                            )


            # ========================================

            if self.router_sock in socks:
                if socks[self.router_sock] in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    conn_id = self.router_sock.recv(zmq.DONTWAIT)
                    req = self.router_sock.recv_json(zmq.DONTWAIT)
                    self.res_queue.append((conn_id, self._handle_request(req)))
                    logging.info(
                        f'Storage {self.id}: Processing incoming request...{req["url"]}')

                if socks[self.router_sock] in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT):
                    try:
                        conn_id, res = self.res_queue.pop(0)
                    except IndexError:
                        pass
                    else:
                        if res is not None:
                            self.router_sock.send(conn_id, zmq.SNDMORE)
                            self.router_sock.send_json(res)
                            logging.info(
                                f'Sended response to {conn_id}: {res["url"]} '
                                f'[{"" if res["hit"] else "not "}hit]'
                            )

            # ========================================

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
            if req['spread']:
                self.upd_queue.append((url, content))

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
