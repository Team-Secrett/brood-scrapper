"""
Tyes for storage nodes.
"""
import os


class Cache:
    """
    Data structure to handle cache operations

    Operations:
        get(filename: str) -> str | None
        set(filename: str, content: str) -> None
    """
    def __init__(self, cache_folder='cache'):
        self.path = f'./{cache_folder}'
        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def get(self, filename: str) -> str:
        with open(os.path.join(self.path, filename), 'r') as fd:
            print(fd.readlines())

    def set(self, filename: str, content: str):
        with open(os.path.join(self.path, filename), 'w') as fd:
            fd.write(content)
