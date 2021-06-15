"""
Client class.
"""
from typing import Dict
import logging
import threading
import time

import zmq
from tornado.ioloop import IOLoop, PeriodicCallback

try:
    from src import settings
    from src import utils
    from src import udp
except ImportError:
    import settings
    import utils
    import udp

logging.basicConfig(
    # format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class WorkerDiscovering:

    def __init__(self, inter_ip, ctx: zmq.Context, pipe: zmq.Socket):
        self.ctx = ctx
        self.pipe_sock = pipe
        self.loop = None
        self.udp = udp.UDPReceiver(
            inter_ip, settings.WORKER_MCAST_ADDR, settings.WORKER_PING_SIZE)
        self.workers: Dict[str, utils.Peer] = {}

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
            self.udp.sock.fileno(), self.handle_beacon, IOLoop.WRITE )

        reaper = PeriodicCallback(self.reap_workers, 1000)
        reaper.start()

        self.loop.start()

    def handle_beacon(self, fd, event):
        data, addr = self.udp.recv()
        flag, wid, wport = data
        addr = (addr[0], int(wport))

        # print('new beacon:', data)

        if flag != 'w':
            return

        if wid in self.workers:
            self.workers[wid].is_alive()

            if self.workers[wid].addr != addr:
                self.workers[wid].update(addr)
                self.pipe_sock.send_json(
                    {
                        'action': 'update',
                        'worker': wid,
                        'addr': addr,
                    }
                )
        else:
            self.workers[wid] = utils.Peer(wid, (addr[0], wport))
            self.pipe_sock.send_json(
                {
                    'action': 'add',
                    'worker': wid,
                    'addr': [addr[0], int(wport)],
                }
            )

    def reap_workers(self):
        now = time.time()
        for w in dict(self.workers):
            worker = self.workers[w]
            if worker.expires_at < now:
                self.workers.pop(worker.uuid)
                self.pipe_sock.send_json(
                    {
                        'action': 'delete',
                        'worker': worker.uuid,
                    }
                )
                logging.info(f'Reaped worker {worker.uuid}')


class UrlFeeder:

    def __init__(self, fp):
        self.buffer = []

        with open(fp, encoding='utf8') as f:
            for line in f:
                self.buffer.append(line[:-1])

    def feed(self):
        try:
            return self.buffer.pop(0)
        except IndexError:
            return None

    # TODO: Add pendent requests


class Client:
    """
    Represent a client node in the system.
    Send requests with url and expects the HTML code.
    """

    def __init__(self, ip, port, url_file):
        self.address = (ip, port)
        self.ctx = zmq.Context()

        self.sender_sock = None     # talk to workers
        self.pipe_sock = None       # talk to discovering service

        self.workers = {}           # workers discovered so far

        self.discoverer = None    # discovering service

        self.feeder = UrlFeeder(url_file)

    def start(self):
        """
        Start client services and bind its interfaces.
        """
        self.sender_sock = self.ctx.socket(zmq.DEALER)

        self.pipe_sock, pipe_sock = utils.pipe(self.ctx)

        self.discoverer = WorkerDiscovering(
            self.address[0], self.ctx, pipe_sock)
        threading.Thread(
            target=self.discoverer.start, name='Discoverer').start()
        logging.info('Discovering service started...')

        poller = zmq.Poller()
        poller.register(self.pipe_sock, zmq.POLLIN)
        poller.register(self.sender_sock, zmq.POLLIN | zmq.POLLOUT)

        while True:
            socks = dict(poller.poll())

            # process the updates from workers discovering service
            if self.pipe_sock in socks and socks[self.pipe_sock]:
                msg = self.pipe_sock.recv_json()

                action = msg['action']
                wid = msg['worker']
                try:
                    addr = tuple(msg.get('addr'))
                except TypeError:
                    if action in ('add', 'update'):
                        logging.warning(f'Worker {wid}: update without address')
                        continue
                
                # print()

                if action == 'delete':
                    self.sender_sock.disconnect('tcp://%s:%d' % self.workers[wid])
                    self.workers.pop(wid)
                    logging.info(f'Removed worker {wid}')

                elif action == 'add':
                    self.sender_sock.connect('tcp://%s:%d' % addr)
                    self.workers[wid] = addr
                    logging.info(f'Added worker {wid}: {addr}')

                elif action == 'update' and False:  # TODO: breaking with 2+ workers
                    self.sender_sock.disconnect('tcp://%s:%d' % self.workers[wid])
                    self.sender_sock.connect('tcp://%s:%d' % addr)
                    old_addr, self.workers[wid] = self.workers[wid], addr
                    logging.info(f'Updated worker {wid}: {old_addr} -> {addr}')

            if self.sender_sock in socks:
                event = socks[self.sender_sock]

                # process the responses from workers
                if event in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    data = self.sender_sock.recv_json()
                    self._save(data)
                    logging.info(f'Received {data["url"]} html code')

                # make a request to workers
                if event in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT) and self.workers:
                    url = self.feeder.feed()
                    if url:
                        self.sender_sock.send_json(
                            {
                                'url': url,
                            }
                        )
                        logging.info(f'Requested {url}')
                        time.sleep(1)   # TODO: remove this

    def _save(self, data):
        """
        How must be saved html code received
        """
        pass


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 3:
        _, ip, port, url_file = sys.argv

        client = Client(ip, int(port), url_file)

        client.start()
