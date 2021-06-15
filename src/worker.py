import logging
import threading
import time

import zmq

try:
    from src import udp
    from src import settings
    from src import utils
except ImportError:
    import udp
    import settings
    import utils


logging.basicConfig(
    # format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    format='[%(levelname)s]: %(message)s',
    level=logging.INFO
)


class Worker:

    def __init__(self, ip, port):
        self.address = (ip, port)
        self.ctx = zmq.Context()

        self.rcver_sock = None      # talk to clients
        self.ping_sender = None     # send beacons to workers mcast group

        self.id = utils.random_id()

    def start(self):
        self.sock = self.ctx.socket(zmq.ROUTER)
        self.sock.bind('tcp://%s:%d' % self.address)
        logging.info(f'Binded to {self.address}\tID: {self.id}')

        self.ping_sender = udp.UDPSender(
            self.id,
            self.address[1],
            self.address[0],
            settings.WORKER_MCAST_ADDR
        )
        threading.Thread(
            target=self.ping_sender.start, name='Pinger').start()
        logging.info('Ping service started...')

        while True:
            cid = self.sock.recv()
            request = self.sock.recv_json()

            if 'url' in request:
                # scrap url
                html = f'<h1>html code for {request["url"]}</h1>'
                resp = {
                    'url': request['url'],
                    'html': html,
                }
                time.sleep(1)
            else:
                resp = {
                    'error': 'invalid request',
                }

            self.sock.send(cid, zmq.SNDMORE)
            self.sock.send_json(resp)
            logging.info(
                f'Served request from {cid}: '
                f'{resp.get("url") or resp.get("error")}'
            )


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 2:
        _, ip, port = sys.argv

        worker = Worker(ip, int(port))

        worker.start()
