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
            logger.debug(f"start ServerMS: {socket_path}")
            threads.append(thread)
        for thread in threads:
            thread.join()
        logger.info(f"all ServerMS stopped")
        