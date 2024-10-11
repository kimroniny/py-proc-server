import requests
import threading
session = requests.Session()

def test_get():
    url = "http://localhost:8888/async"
    resp = session.get(url, params={'msg': 'hello'})
    print(resp.text)

def test_get_async_multi_threads():
    def get_async():
        url = "http://localhost:8888/async"
        resp = session.get(url, params={'msg': 'hello'})
        print(resp.text)

    threads = []
    for i in range(10):
        t = threading.Thread(target=get_async)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

def test_get_sync_multi_threads():
    def get_sync():
        url = "http://localhost:8888/sync"
        resp = session.get(url, params={'msg': 'hello'})
        print(resp.text)

    threads = []
    for i in range(10):
        t = threading.Thread(target=get_sync)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

if __name__ == "__main__":
    test_get_sync_multi_threads()

