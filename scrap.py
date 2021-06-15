import requests
from requests import Response


def get(url: str, params: dict = {}, timeout: float = None) -> Response:
    return requests.get(url, params, timeout=timeout).content


if __name__ == '__main__':
    response = get('https://www.google.com', timeout=5)
    print(response)
