import zmq
from settings import (
    PUB_SUB_CHANNEL_NAME,
    STORAGE_MCAST_ADDR
)
import udp
import utils
import threading
import logging


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
                inp = self.sub_sock.recv_string()
                print(inp)


if __name__ == '__main__':
    storage = Storage('192.168.43.242', 5001)

    try:
        storage.start()
    except KeyboardInterrupt:
        logging.info('\nClosing storage node...')
