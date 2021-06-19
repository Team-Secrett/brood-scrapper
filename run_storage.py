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
    '--port', type=int, required=True,
    help='Port to listen workers connections'
)
parser.add_argument(
    '--cache', type=str, default='cache',
    help='Cache folder path'
)
parser.add_argument(
    '--update', action='store_true',
    help='If present this storage will update his cache'
)
args = parser.parse_args()

storage = Storage(args.ip, args.port, args.cache, args.update)

storage.start()
try:
    storage.start()
except KeyboardInterrupt:
    print('>>> Stopped by user!')
