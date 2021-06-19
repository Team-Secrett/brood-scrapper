import logging
import threading

import zmq

from src import settings
from src.utils.udp import UDPSender
from src.utils.worker import StorageDisc, RequestsMonitor, Scrapper
from src.utils.functions import random_id, pipe

logging.basicConfig(
    # format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class Worker:

    def __init__(self, ip, port):
        self.id = random_id()
        self.address = (ip, port)
        self.ctx = zmq.Context()

        self.cli_sock = None        # talk to clients
        self.ping_sender = None     # send beacons to workers mcast group

        self.st_sock = None     # talk to storage
        self.disc_sock = None   # recv updates of storages up and down

        self.discoverer = None  # storage discovering service
        self.storages = {}      # storages discovered so far

        self.monitor = RequestsMonitor()
        self.pendant_updates = []

    def start(self):
        """
        Start worker services and bind its interfaces.
        """
        # start scrapper thread
        threading.Thread(
            target=Scrapper.start_scrapper, args=(self.monitor, ), name='Scrapper'
        ).start()
        logging.info('Scrapper started...')

        # start caching pruner thread
        threading.Thread(
            target=self.monitor.prune_caching, name='Caching-Pruner'
        ).start()

        # start sock to talk with storage
        self.st_sock = self.ctx.socket(zmq.DEALER)

        # start storage discovering service
        self.disc_sock, pipe_sock = pipe(self.ctx)
        self.discoverer = StorageDisc(self.address[0], pipe_sock)
        threading.Thread(
            target=self.discoverer.start, name='Discoverer'
        ).start()
        logging.info('Storage discovering serivce started...')

        # start sock to talk with clients
        self.cli_sock = self.ctx.socket(zmq.ROUTER)
        self.cli_sock.bind('tcp://%s:%d' % self.address)
        logging.info(f'Binded to {self.address}\tID: {self.id}')

        # start ping to clients service
        self.ping_sender = UDPSender(
            'w',
            self.id,
            self.address[1],
            self.address[0],
            settings.WORKER_MCAST_ADDR
        )
        threading.Thread(
            target=self.ping_sender.start, name='Ping-Workers'
        ).start()
        logging.info('Ping service started...')

        # create a poller for handling events in sockets
        poller = zmq.Poller()
        poller.register(self.disc_sock, zmq.POLLIN)
        poller.register(self.st_sock, zmq.POLLIN | zmq.POLLOUT)
        poller.register(self.cli_sock, zmq.POLLIN | zmq.POLLOUT)

        while True:
            socks = dict(poller.poll())

            # =============================================

            # process messages from storage discovering service
            if self.disc_sock in socks:
                msg = self.disc_sock.recv_json(zmq.DONTWAIT)

                # get action, storage id and addr (if present)
                action = msg['action']
                sid = msg['peer']
                try:
                    addr = tuple(msg.get('addr'))
                except TypeError:
                    if action in ('add', 'update'):
                        logging.warning(f'Storage {sid}: update without address')
                        continue

                # storage is not longer accessible, close the connection
                if action == 'delete':
                    self.st_sock.disconnect('tcp://%s:%d' % self.storages[sid])
                    self.storages.pop(sid)
                    logging.info(f'Removed storage {sid}')

                # new worker, establish a connection
                elif action == 'add':
                    self.st_sock.connect('tcp://%s:%d' % addr)
                    self.storages[sid] = addr
                    print('tcp://%s:%d' % addr)
                    logging.info(f'Added storage {sid}: {addr}')

                # worker changed his interface, update the conection
                elif action == 'update':  # TODO: breaking with 2+ storages
                    self.st_sock.disconnect('tcp://%s:%d' % self.storages[sid])
                    self.st_sock.connect('tcp://%s:%d' % addr)
                    old_addr, self.storages[sid] = self.storages[sid], addr
                    logging.info(f'Updated storage {sid}: {old_addr} -> {addr}')

            # =============================================

            if not self.storages:
                self.monitor.move_new_to_scrapping()

            # send/receive messages to/from storage
            elif self.st_sock in socks:
                # receive response from storage
                if socks[self.st_sock] in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    res = self.st_sock.recv_json(zmq.DONTWAIT)

                    try:
                        if res['hit']:
                            id_url = (res['id'], res['url'])
                            self.monitor.move_caching_to_ready(id_url, res['content'])
                    except KeyError:
                        logging.warning('Bad response from cache')

                # send update/request to storage
                if socks[self.st_sock] in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT):
                    # send updates if there is someone
                    while self.pendant_updates:
                        url, content = self.pendant_updates.pop(0)
                        self.st_sock.send_json(
                            {
                                "url": url,
                                "content": content,
                            }
                        )
                        logging.info(f'Updated cache: {url}')

                    # send request to cache if there is in queue
                    id_url = self.monitor.new_next()
                    if id_url is not None:
                        self.st_sock.send_json(
                            {
                                "id": id_url[0],
                                "url": id_url[1],
                            }
                        )
                        # logging.info(f'Requested to cache: {id_url[1]}')

            # =============================================

            # send/receive messages to/from clients
            if self.cli_sock in socks:
                # receive request from client
                if socks[self.cli_sock] in (zmq.POLLIN, zmq.POLLIN | zmq.POLLOUT):
                    conn_id = self.cli_sock.recv(zmq.DONTWAIT)
                    req = self.cli_sock.recv_json(zmq.DONTWAIT)

                    try:
                        self.monitor.add_new((req['id'], req['url']), conn_id)
                        logging.info(f'Enqueued request from {conn_id}: {req["url"]}')
                    except KeyError:
                        logging.warning(f'Bad request from {conn_id}')

                # send response to client
                if socks[self.cli_sock] in (zmq.POLLOUT, zmq.POLLIN | zmq.POLLOUT):
                    id_url, req = self.monitor.ready_next()
                    if id_url is not None and req is not None:
                        self.cli_sock.send(req.client_conn, zmq.SNDMORE)
                        self.cli_sock.send_json(
                            {
                                "url": id_url[1],
                                "hit": req.hit,
                                "content": req.content,
                            }
                        )
                        logging.info(
                            f'Served request from {req.client_conn}: {id_url[1]} '
                            f'{"[hit]" if req.hit else "[not hit]"}'
                        )
                        self.pendant_updates.append((id_url[1], req.content))


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 2:
        _, ip, port = sys.argv

        worker = Worker(ip, int(port))

        worker.start()
