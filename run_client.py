"""
Main entry point for run a client node.
"""
from argparse import ArgumentParser

from src.client import Client


parser = ArgumentParser()

parser.add_argument(
    '--ip', type=str, required=True,
    help='Interface IP address'
)
parser.add_argument(
    '--file', type=str,
    help='File with URLs to be loaded'
)
parser.add_argument(
    '--n', type=int, default=-1,
    help='Max number of URLs to load. Default -1, load all'
)
parser.add_argument(
    '--depth', type=int, default=3,
    help='Max depth scrapping urls in file. Default 3'
)

args = parser.parse_args()

client = Client(args.ip, args.file, args.n, args.depth)

try:
    client.start()
except KeyboardInterrupt:
    print('>>> Stopped by user!')
