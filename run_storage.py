from src.storage import Storage


storage = Storage('192.168.43.242', 5001)

try:
    storage.start()
except KeyboardInterrupt:
    print('\nClosing storage node...')
