"""
Tyes for storage nodes.
"""
import os
import re


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
        filename = re.sub('https?://', '', filename)
        filename = re.sub(r'\?|/', '_', filename)
        try:
            with open(os.path.join(self.path, filename), 'r') as fd:
                return fd.read()
        except FileNotFoundError:
            return None

    def set(self, filename: str, content: str):
        filename = re.sub('https?://', '', filename)
        filename = re.sub(r'\?|/', '_', filename)
        with open(os.path.join(self.path, filename), 'w') as fd:
            fd.write(content)

    def __iter__(self):
        for file in os.listdir(self.path):
            with open(f'{self.path}/{file}') as fd:
                content = fd.read()
                yield (file, content)


if __name__ == '__main__':
    cache = Cache()

    for file, content in cache:
        print(file, content)
