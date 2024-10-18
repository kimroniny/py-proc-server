import sys, os
sys.path.insert(0, os.path.abspath('./unix_server'))
from concurrent.futures import ThreadPoolExecutor, wait as wait_futures
from server.server_ms_thread_wrapper import ServerMSThreadWrapper
from client.client_ms import ClientMS
from loguru import logger
import time
import multiprocessing

logger.remove()
logger.add(sys.stdout, level="INFO")

def start_server():
    def start(socket_paths):
        server = ServerMSThreadWrapper(routes=[], max_workers=30, max_conns=30)
        server.start(socket_paths, stop_event)
    stop_event = multiprocessing.Event()
    all_socket_paths = []
    procs = []
    for i in range(100):
        socket_paths = [f"/tmp/test_unix_{i}_{j}" for j in range(1)]
        proc = multiprocessing.Process(target=start, args=(socket_paths, ))
        proc.start()
        procs.append(proc)
        all_socket_paths.append(socket_paths)
    return procs, all_socket_paths, stop_event

def create_clients(all_socket_paths):
    def create(socket_paths):
        client = ClientMS(socket_paths)
    with ThreadPoolExecutor(max_workers=30) as executor:
        # return list(executor.map(lambda _: create(), range(100)))
        futures = [executor.submit(create, socket_paths) for socket_paths in all_socket_paths]
        wait_futures(futures)

def test_connect_latency():
    procs, all_socket_paths, stop_event = start_server()
    time.sleep(1)
    start = time.time()
    create_clients(all_socket_paths)
    end = time.time()
    print(f"connect latency: {end - start}")
    stop_event.set()
    for proc in procs:
        proc.join()

if __name__ == "__main__":
    test_connect_latency()