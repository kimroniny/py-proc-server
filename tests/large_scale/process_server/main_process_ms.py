import time
import threading
import sys
import traceback
import multiprocessing
import cProfile
from typing import List
from loguru import logger
from client.client_ms import ClientMS
from tests.large_scale.process_server.calc_handler import CalcHandler
from service.api_service_ms import ApiService as ApiServiceMS
from multiprocessing.synchronize import Event as ProcessEventType
from multiprocessing import Process, Event as ProcessEvent
from multiprocessing import Manager
from concurrent.futures import ThreadPoolExecutor, wait as wait_futures

multiprocessing.set_start_method('fork')

NUM_API_SERVICES = 1
NUM_MULTI_SOCKET = 5
NUM_WORKERS_PER_API_SERVICE = 25 
NUM_MAX_CONNS = 100000
# NUM_CLIENTS = NUM_API_SERVICES
NUM_CLIENTS = 800
NUM_REQUESTS_PER_CLIENT = 500
NUM_THREADS_PER_CLIENT = 25
CALC_TARGET = 1000


logger.remove()  # Remove the default logger
logger.add(sys.stderr, level="INFO")  # Set logger to only show INFO level logs

def start_api_services():

    def listen_stop_proc_event(stop_event: ProcessEventType, api_service: ApiServiceMS):
        while not stop_event.is_set():
            time.sleep(1)
        api_service.stop()

    def start_single_api_service(i, stop_event: ProcessEventType, socket_paths: List[str]):
        args = {}
        max_workers = NUM_WORKERS_PER_API_SERVICE
        max_conns = NUM_MAX_CONNS
        api_service = ApiServiceMS([CalcHandler], socket_paths, max_workers, max_conns)
        listen_thread = threading.Thread(target=listen_stop_proc_event, args=(stop_event, api_service))
        listen_thread.start()
        api_service.run(args)
        listen_thread.join()
        # print(f"api service {i} stopped")

    processes = []
    process_events = []
    socket_paths = []
    for i in range(NUM_API_SERVICES):
        stop_event = ProcessEvent()
        socket_paths_each_api_service = [f"/tmp/server_socket_{i}_{j}" for j in range(NUM_MULTI_SOCKET)]
        p = Process(target=start_single_api_service, args=(i, stop_event, socket_paths_each_api_service))
        p.start()
        processes.append(p)
        process_events.append(stop_event)
        socket_paths.append(socket_paths_each_api_service)

    return processes, process_events, socket_paths

def send_requests(socket_paths: List[List[str]]):
    
    def single_client_to_single_api_service(client: ClientMS):
        cnt = 0
        try:
            data = {'target': CALC_TARGET, 'text': 'hello world'*10000}
            for i in range(NUM_REQUESTS_PER_CLIENT):
                cnt += 1
                resp = client.post('/calc', data)
                # time.sleep(0.001)
                if resp.code != 200:
                    logger.error(resp.err)
                else:
                    logger.debug(resp.msg)
                    # print(resp.msg)
        except Exception as e:
            logger.error(traceback.format_exc())

        # print(f"cnt: {cnt}")

    def send_requests_from_single_client(client_id: int):
        clients = []
        for socket_paths_each_api_service in socket_paths:
            socket_paths_for_client = [socket_paths_each_api_service[client_id % len(socket_paths_each_api_service)]]
            client = ClientMS(socket_paths_for_client)
            clients.append(client)
        
        # 所有client进程在这里要同步, 然后再测试后面的发请求性能
        # with lock:
        #     proc_val.value += 1
        
        # while True:
        #     if proc_val.value >= NUM_CLIENTS:
        #         break
        #     time.sleep(0.01)

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS_PER_CLIENT) as executor:
            futures = []
            for client in clients:
                futures.append(executor.submit(single_client_to_single_api_service, client))
            wait_futures(futures)
        end_time = time.time()
        cost = end_time - start_time
        print(f"time taken({client_id}): {cost}")
        proc_queue.put(cost)

    processes = []
    proc_queue = multiprocessing.Queue()
    # proc_val = multiprocessing.Value('i', 0)
    # lock = multiprocessing.Lock()
    for idx in range(NUM_CLIENTS):
        p = Process(target=send_requests_from_single_client, args=(idx,), name=f"process-{idx}")
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
    
    # analysis
    costs = []
    while not proc_queue.empty():
        cost = proc_queue.get()
        costs.append(cost)
    
    print(f"costs: {costs}")
    print(f"mean: {sum(costs) / len(costs)}")
if __name__ == "__main__":
    processes, process_events, socket_paths = start_api_services()
    time.sleep(1)
    
    send_requests(socket_paths)

    for event in process_events:
        event.set()
    for p in processes:
        p.join()
    
    print("all api services and clients stopped")

