from __future__ import annotations
import json
import sys
import asyncio
import threading
import time
from typing import Dict, Optional, List
from server.server_ms import ServerMS, Handler
from server.server_ms_thread_wrapper import ServerMSThreadWrapper
from loguru import logger
from typing import Dict

class ApiService(object):
    def __init__(self, handlers: List[Handler], socket_paths: List[str], max_workers: Optional[int] = None, max_conns: Optional[int] = None) -> None:
        self.handlers = handlers
        self.socket_paths = socket_paths
        self.max_workers = max_workers
        self.max_conns = max_conns
        self.stop_event: threading.Event = None

    def make_server(self, args: Dict = None) -> ServerMSThreadWrapper:
        if args is None:
            args = {}
        routes = []
        for handler in self.handlers:
            routes += [(route, handler, args) for route in handler.routers().keys()]
        return ServerMSThreadWrapper(routes, max_workers=self.max_workers, max_conns=self.max_conns)

    async def run_app(self, args: Dict = None):
        if args is None:
            args = {}
        server = self.make_server(args)
        self.stop_event = threading.Event() if not self.stop_event else self.stop_event
        server_thread = threading.Thread(target=server.start, args=(self.socket_paths, self.stop_event))
        server_thread.daemon = True
        server_thread.start()
        logger.info(f"api service({self.socket_paths}) is listening...")
        """
        # self.stop_event.wait() # 使用 wait 会阻塞, 导致异步程序无法执行
        """
        while not self.stop_event.is_set():
            await asyncio.sleep(1)
        logger.info(f"api service stop event is set")
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
