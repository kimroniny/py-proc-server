from __future__ import annotations
import json
import sys
import asyncio
import threading
import time
from typing import Dict, Optional
from server.server import Server, Handler
from loguru import logger
from typing import Dict
from example.application_response import StandardResponse

logger.remove()  # Remove the default logger
logger.add(sys.stderr, level="INFO")  # Set logger to only show INFO level logs


class MyHandler(Handler):
    @classmethod
    def routers(cls) -> Dict[str, str]:
        return {
            r'/': cls.hello,
        }

    def __get_func(self) -> callable:
        path = self.get_url()
        routers = self.routers()
        callfunc = routers.get(path, None)
        if callfunc is None:
            raise Exception("invalid uri:'{}'".format(path))
        return callfunc

    def get(self):
        self.__call_func()
    
    def post(self):
        self.__call_func()

    def __call_func(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    def hello(self):
        msg = self.get_argument('msg')
        logger.debug(f"recv msg in handler: {msg}")
        # time.sleep(1)
        return f'server recv msg: {msg}'

class ApiService(object):
    def __init__(self, socket_path: str, max_workers: Optional[int] = None, max_conns: Optional[int] = None) -> None:
        self.socket_path = socket_path
        self.max_workers = max_workers
        self.max_conns = max_conns
        self.stop_event: threading.Event = None

    def make_server(self, args: Dict = None) -> Server:
        if args is None:
            args = {}
        handlers = [
            MyHandler,
        ]
        routes = []
        for handler in handlers:
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

if __name__ == "__main__":
    args = {}
    socket_path = "/tmp/server_socket"
    max_workers = 100
    api_service = ApiService(socket_path, max_workers)
    api_service.run(args)