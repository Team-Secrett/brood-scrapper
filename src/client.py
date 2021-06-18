"""
Client class.
"""
import logging
import threading
import time

import zmq

from src.utils.client import UrlFeeder, WorkerDisc
from src.utils.functions import random_id, pipe


logging.basicConfig(
    # format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class Client:
    """
    Represent a client node in the system.
    Send requests with url and expects the HTML code.
    """

    def __init__(self, ip, url_file, n):
        self.id = random_id()
        self.inter_ip = ip
        self.ctx = zmq.Context()

        self.sender_sock = None     # talk to workers
        self.pipe_sock = None       # talk to discovering service

        self.workers = {}           # workers discovered so far

        self.discoverer = None      # discovering service

        self.feeder = UrlFeeder(url_file, n)

    def start(self):
        """
        Start client services and bind its interfaces.
        """
        self.sender_sock = self.ctx.socket(zmq.DEALER)
        # self.pipe_sock.setsockopt_string(zmq.IDENTITY, self.id)

        self.pipe_sock, pipe_sock = pipe(self.ctx)

        self.discoverer = WorkerDisc(self.inter_ip, pipe_sock)
        threading.Thread(
            target=self.discoverer.start, name='Discoverer').start()
        logging.info('Discovering service started...')

        poller = zmq.Poller()
        poller.register(self.pipe_sock, zmq.POLLIN)
        poller.register(self.sender_sock, zmq.POLLIN | zmq.POLLOUT)

        while True:
            socks = dict(poller.poll())

            # process the updates from workers discovering service
            if self.pipe_sock in socks:
                msg = self.pipe_sock.recv_json(zmq.DONTWAIT)

                # get action, worker id and addr (if is present)
                action = msg['action']
                wid = msg['peer']
                try:
                    addr = tuple(msg.get('addr'))
                except TypeError:
                    if action in ('add', 'update'):
                        logging.warning(f'Worker {wid}: update without address')
                        continue

                # worker is not longer accessible, close the connection
                if action == 'delete':
                    self.sender_sock.disconnect('tcp://%s:%d' % self.workers[wid])
                    self.workers.pop(wid)
                    logging.info(f'Removed worker {wid}')

                # new worker, establish a connection
                elif action == 'add':
                    self.sender_sock.connect('tcp://%s:%d' % addr)
                    self.workers[wid] = addr
                    logging.info(f'Added worker {wid}: {addr}')

                # worker changed his interface, update the conection
                elif action == 'update':
                    self.sender_sock.disconnect('tcp://%s:%d' % self.workers[wid])
                    self.sender_sock.connect('tcp://%s:%d' % addr)
                    old_addr, self.workers[wid] = self.workers[wid], addr
                    logging.info(f'Updated worker {wid}: {old_addr} -> {addr}')

            if self.sender_sock in socks:
                event = socks[self.sender_sock]

                # process the responses from workers
                if event in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    try:
                        res = self.sender_sock.recv_json(zmq.DONTWAIT)
                    except zmq.error.Again:
                        pass
                    else:
                        if 'url' in res:
                            self.feeder.done(res['url'])
                            self._save(res['content'])
                            logging.info(f'Received {res["url"]}. Missing: {len(self.feeder)}')
                        else:
                            logging.warning(f'Received: {res.get("error", "error")}')

                # make a request to workers
                if event in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT) and self.workers:
                    url = self.feeder.feed()
                    if url:
                        self.sender_sock.send_json(
                            {
                                'id': self.id,
                                'url': url,
                            }
                        )
                        logging.info(f'Requested {url}')
                        time.sleep(1)   # TODO: remove this

            if not self.feeder:
                logging.info('>>> Done!')
                break

    def _save(self, data):
        """
        How must be saved html code received
        """
        pass
