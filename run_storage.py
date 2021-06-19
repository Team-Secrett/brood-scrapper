"""
Main entry point for run a storage node.
"""
from argparse import ArgumentParser

from src.storage import Storage


parser = ArgumentParser()

parser.add_argument(
    '--ip', type=str, required=True,
    help='Interface IP address'
)
parser.add_argument(
    '--wport', type=int, required=True,
    help='Port to listen workers connections'
)
parser.add_argument(
    '--sport', type=int, required=True,
    help='Port to listen other workers connections'
)

args = parser.parse_args()

storage = Storage(args.ip, args.wport, args.sport)

storage.start()
try:
    storage.start()
except KeyboardInterrupt:
    print('>>> Stopped by user!')
