from __future__ import annotations
import json
import sys
import asyncio
import threading
import time
from typing import Dict, Optional, List
from server.server import Server, Handler
from loguru import logger
from typing import Dict
from example.application_response import StandardResponse

class ApiService(object):
    def __init__(self, handlers: List[Handler], socket_path: str, max_workers: Optional[int] = None, max_conns: Optional[int] = None) -> None:
        self.handlers = handlers
        self.socket_path = socket_path
        self.max_workers = max_workers
        self.max_conns = max_conns
        self.stop_event: threading.Event = None

    def make_server(self, args: Dict = None) -> Server:
        if args is None:
            args = {}
        routes = []
        for handler in self.handlers:
            routes += [(route, handler, args) for route in handler.routers().keys()]
        return Server(routes, max_workers=self.max_workers, max_conns=self.max_conns)

    async def run_app(self, args: Dict = None):
        if args is None:
            args = {}
        server = self.make_server(args)
        self.stop_event = threading.Event()
        server_thread = threading.Thread(target=server.start, args=(self.socket_path, self.stop_event))
        server_thread.daemon = True
        server_thread.start()
        logger.info(f"api service({self.socket_path}) is listening...")
        self.stop_event.wait()
        logger.info(f"api service({self.socket_path}) stopped!")

    def stop(self) -> None:
        assert self.stop_event is not None
        self.stop_event.set()

    def run(self, args: Dict) -> None:
        try:
            asyncio.run(self.run_app(args))
        except (KeyboardInterrupt, SystemExit):
            logger.info("api service stopped!")
