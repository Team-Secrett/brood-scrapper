import zmq
from settings import (
    PUB_SUB_CHANNEL_NAME,
    STORAGE_MCAST_ADDR
)
import udp
import utils
from utils import Cache
import threading
import logging
import json


logging.basicConfig(
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class Storage:
    """
    Represents a storage node in the system.
    Manage url caching
    """

    def __init__(self, ip, port):
        self.address = (ip, port)
        self.ctx = zmq.Context()
        self.sub_sock = None
        self.id = utils.random_id()
        self.ping_sender = None

        self.cache = Cache()

    def connect_sub(self):
        self.sub_sock = self.ctx.socket(zmq.SUB)
        self.sub_sock.connect('tcp://%s:%d' % self.address)
        self.sub_sock.subscribe(PUB_SUB_CHANNEL_NAME)
        print('Subscriber: Connecting to %s:%d...' % self.address)

    def init_ping_sender(self):
        self.ping_sender = udp.UDPSender(
            self.id,
            self.address[1],
            self.address[0],
            STORAGE_MCAST_ADDR
        )
        threading.Thread(target=self.ping_sender.start, name='Pinger').start()
        logging.info(f'Storage {self.id}: Ping service started...')

    def start(self):
        """
        Start storage service
        """
        self.connect_sub()

        poller = zmq.Poller()
        poller.register(self.sub_sock, zmq.POLLIN | zmq.POLLOUT)

        self.init_ping_sender()

        while True:
            socks = dict(poller.poll())

            if self.sub_sock in socks:
                rec = self.sub_sock.recv_multipart()
                data = json.loads(rec[1])

                try:
                    url, content = data['url'], data['content']
                    self.cache.set(url, content)
                    logging.info(f'Added {url} content to cache...')
                except KeyError:
                    logging.info(
                        f'Storage {self.id}: Received malformed data...')
                    continue


if __name__ == '__main__':
    storage = Storage('192.168.43.242', 5001)

    try:
        storage.start()
    except KeyboardInterrupt:
        logging.info('\nClosing storage node...')
