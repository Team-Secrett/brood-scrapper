"""
Settings of the system.
"""
PEER_EXPIRY = 5.0

WORKER_MCAST_GROUP = '224.1.1.1'
WORKER_MCAST_PORT = 4040
WORKER_MCAST_ADDR = (
    WORKER_MCAST_GROUP,
    WORKER_MCAST_PORT
)
WORKER_PING_SIZE = 12
WORKER_REQ_EXPIRY = 2   # request that worker makes to cache expiry time

PUB_SUB_CHANNEL_NAME = 'DB-UPDATE'
STORAGE_MCAST_GROUP = '225.1.1.1'
STORAGE_MCAST_PORT = 4041
STORAGE_MCAST_ADDR = (
    STORAGE_MCAST_GROUP,
    STORAGE_MCAST_PORT
)
STORAGE_PING_SIZE = 12
