import threading
import multiprocessing
from loguru import logger
from typing import List
from server.server_ms import ServerMS

class ServerMSThreadWrapper:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def start(self, socket_paths: List[str], stop_event: threading.Event):
        threads = []
        for socket_path in socket_paths:
            server = ServerMS(*self._args, **self._kwargs)
            thread = threading.Thread(target=server.start, args=([socket_path], stop_event))
            thread.start()
            threads.append(thread)
        logger.debug(f"start ServerMS: {socket_paths}")
        for thread in threads:
            thread.join()
        logger.debug(f"all ServerMS stopped")
        