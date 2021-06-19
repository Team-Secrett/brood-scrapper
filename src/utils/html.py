import re
from urllib.parse import urlparse


class HTMLParser:
    @staticmethod
    def links(content: str):
        url_regex = r'(http[s]?://(?!youtube|vimeo)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)'
        
        matchs = re.findall(url_regex, content)

        return list(matchs)


class URLParser:
    @staticmethod
    def same_domain(url1: str, url2 :str) -> bool:
        print(urlparse(url1).netloc)
        print(urlparse(url2).netloc)
        return urlparse(url1).netloc == urlparse(url2).netloc

    def netloc(url: str):
        return urlparse(url).netloc


if __name__ == '__main__':
    # content = '<a href="https://github.com">github page</a> <a href="www.google.com">Google</a>'

    # print(HTMLParser.links(content))
    print(URLParser.same_domain('https://github.com/asd/vsd', 'https://github.com/jjjd/asd'))