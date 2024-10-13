from __future__ import annotations
import json
import sys
import asyncio
import threading
import time
from typing import Dict, Optional, List
from server.server_ms import ServerMS, Handler
from loguru import logger
from typing import Dict

class ApiService(object):
    def __init__(self, handlers: List[Handler], socket_paths: List[str], max_workers: Optional[int] = None, max_conns: Optional[int] = None) -> None:
        self.handlers = handlers
        self.socket_paths = socket_paths
        self.max_workers = max_workers
        self.max_conns = max_conns
        self.stop_event: threading.Event = None

    def make_server(self, args: Dict = None) -> ServerMS:
        if args is None:
            args = {}
        routes = []
        for handler in self.handlers:
            routes += [(route, handler, args) for route in handler.routers().keys()]
        return ServerMS(routes, max_workers=self.max_workers, max_conns=self.max_conns)

    async def run_app(self, args: Dict = None):
        if args is None:
            args = {}
        server = self.make_server(args)
        self.stop_event = threading.Event()
        server_thread = threading.Thread(target=server.start, args=(self.socket_paths, self.stop_event))
        server_thread.daemon = True
        server_thread.start()
        logger.info(f"api service({self.socket_paths}) is listening...")
        self.stop_event.wait()
        server_thread.join()
        logger.info(f"api service({self.socket_paths}) stopped!")

    def stop(self) -> None:
        assert self.stop_event is not None
        self.stop_event.set()

    def run(self, args: Dict) -> None:
        try:
            asyncio.run(self.run_app(args))
        except (KeyboardInterrupt, SystemExit):
            logger.info("api service stopped!")
