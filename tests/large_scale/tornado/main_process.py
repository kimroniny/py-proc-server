import time
import threading
import requests
import sys
import multiprocessing
import asyncio
from typing import List
from loguru import logger
from client.client import Client
from tests.large_scale.tornado.api_service import ApiService
from multiprocessing.synchronize import Event as ProcessEventType
from multiprocessing import Process, Event as ProcessEvent
from concurrent.futures import ThreadPoolExecutor, wait as wait_futures

multiprocessing.set_start_method('fork')

NUM_API_SERVICES = 2
# NUM_WORKERS_PER_API_SERVICE = 25 
NUM_CLIENTS = NUM_API_SERVICES
NUM_REQUESTS_PER_CLIENT = 10
NUM_THREADS_PER_CLIENT = 25
CALC_TARGET = 1000


INFO_LEVEL = "INFO"
DEBUG_LEVEL = "DEBUG"
logger.remove()  # Remove the default logger
logger.add(sys.stderr, level=INFO_LEVEL)  # Set logger to only show INFO level logs

def start_api_services():

    def listen_stop_proc_event(stop_event: ProcessEventType, api_service: ApiService):
        while not stop_event.is_set():
            time.sleep(1)
        api_service.stop()

    def start_single_api_service(i, stop_event: ProcessEventType, port: int):
        
        api_service = ApiService()
        listen_thread = threading.Thread(target=listen_stop_proc_event, args=(stop_event, api_service))
        listen_thread.start()
        args = {}
        args['port'] = port
        api_service.run(args)
        listen_thread.join()
        logger.debug(f"api service {i} stopped")

    processes = []
    process_events = []
    api_ports = []
    for i in range(NUM_API_SERVICES):
        stop_event = ProcessEvent()
        port = 8888 + i
        p = Process(target=start_single_api_service, args=(i, stop_event, port))
        p.start()
        processes.append(p)
        process_events.append(stop_event)
        api_ports.append(port)

    return processes, process_events, api_ports

def send_requests(api_ports: List[int]):
    
    def single_client_to_single_api_service(url: str):
        # print(f"send requests to {url}")
        session = requests.Session()
        for i in range(NUM_REQUESTS_PER_CLIENT):
            # print(f"send request {i} to {url}")
            resp = session.get(url, params={'msg': CALC_TARGET})
            time.sleep(0.01)
            logger.debug(resp.text)

    def send_requests_from_single_client(client_id: int):
        urls = []
        for api_port in api_ports:
            urls.append(f"http://localhost:{api_port}/async")

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS_PER_CLIENT) as executor:
            futures = []
            for url in urls:
                futures.append(executor.submit(single_client_to_single_api_service, url))
            wait_futures(futures)
        end_time = time.time()
        print(f"time taken({client_id}): {end_time - start_time}")

    processes = []
    for idx in range(NUM_CLIENTS):
        p = Process(target=send_requests_from_single_client, args=(idx,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    processes, process_events, api_ports = start_api_services()
    
    send_requests(api_ports)

    for event in process_events:
        event.set()
    for p in processes:
        p.join()
    
    logger.info("all api services and clients stopped")

