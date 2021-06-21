"""
Main entry point for run a worker node.
"""
from argparse import ArgumentParser

from src.worker import Worker


parser = ArgumentParser()

parser.add_argument(
    '--ip', type=str, required=True,
    help='Interface IP address'
)
parser.add_argument(
    '--port', type=int,
    help='Port to bind'
)

args = parser.parse_args()

worker = Worker(args.ip, args.port)

try:
    worker.start()
except KeyboardInterrupt:
    print('>>> Stopped by user!')
