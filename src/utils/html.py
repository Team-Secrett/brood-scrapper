import re


class HTMLParser:
    @staticmethod
    def links(content: str):
        url_regex = r'href=[\'"]?([^\'" >]+)'
        
        matchs = re.findall(url_regex, content)

        return list(matchs)


if __name__ == '__main__':
    content = '<a href="https://github.com">github page</a> <a href="www.google.com">Google</a>'

    print(HTMLParser.links(content))
