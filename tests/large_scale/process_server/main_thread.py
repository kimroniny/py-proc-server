import time
import threading
import sys
from typing import List
from loguru import logger
from client.client import Client
from tests.large_scale.api_service import ApiService
from concurrent.futures import ThreadPoolExecutor, wait as wait_futures

# multiprocessing.set_start_method('fork')

NUM_API_SERVICES = 200
NUM_WORKERS_PER_API_SERVICE = 50
NUM_CLIENTS = NUM_API_SERVICES
NUM_REQUESTS_PER_CLIENT = 100    
NUM_THREADS_PER_CLIENT = 50
CALC_TARGET = 1000


logger.remove()  # Remove the default logger
logger.add(sys.stderr, level="INFO")  # Set logger to only show INFO level logs

def start_api_services():

    def listen_stop_proc_event(stop_event: threading.Event, api_service: ApiService):
        while not stop_event.is_set():
            time.sleep(1)
        api_service.stop()

    def start_single_api_service(i, stop_event: threading.Event, socket_path: str):
        args = {}
        max_workers = NUM_WORKERS_PER_API_SERVICE
        api_service = ApiService(socket_path, max_workers)
        listen_thread = threading.Thread(target=listen_stop_proc_event, args=(stop_event, api_service))
        listen_thread.start()
        api_service.run(args)
        listen_thread.join()
        # print(f"api service {i} stopped")

    threads = []
    thread_events = []
    socket_paths = []
    for i in range(NUM_API_SERVICES):
        stop_event = threading.Event()
        socket_path = f"/tmp/server_socket_{i}"
        t = threading.Thread(target=start_single_api_service, args=(i, stop_event, socket_path))
        t.start()
        threads.append(t)
        thread_events.append(stop_event)
        socket_paths.append(socket_path)

    return threads, thread_events, socket_paths

def send_requests(socket_paths: List[str]):
    
    def single_client_to_single_api_service(client: Client):
        for i in range(NUM_REQUESTS_PER_CLIENT):
            resp = client.post('/calc', {'target': CALC_TARGET})
            time.sleep(0.01)
            if resp.code != 200:
                logger.error(resp.err)
            else:
                logger.debug(resp.msg)
                pass

    def send_requests_from_single_client(client_id: int):
        clients = []
        for socket_path in socket_paths:
            client = Client(socket_path)
            clients.append(client)

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS_PER_CLIENT) as executor:
            futures = []
            for client in clients:
                futures.append(executor.submit(single_client_to_single_api_service, client))
            wait_futures(futures)
        end_time = time.time()
        print(f"time taken({client_id}): {end_time - start_time}")

    threads = []
    for idx in range(NUM_CLIENTS):
        t = threading.Thread(target=send_requests_from_single_client, args=(idx,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    threads, thread_events, socket_paths = start_api_services()
    
    send_requests(socket_paths)

    for event in thread_events:
        event.set()
    for t in threads:
        t.join()
    
    print("all api services and clients stopped")

