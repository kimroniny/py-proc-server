from __future__ import annotations
import json
import sys
import asyncio
import threading
import time
import argparse
from typing import Dict, Optional
from server.server import Server, Handler
from loguru import logger
from typing import Dict
from example.application_response import StandardResponse
from service.api_service import ApiService
from service.api_service_ms import ApiService as ApiServiceMS

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


def getArgs():
    parser = argparse.ArgumentParser(description="api service")
    parser.add_argument("--ms", action="store_true", help="multi socket")
    return parser.parse_args()

if __name__ == "__main__":
    args = {}
    socket_path = "/tmp/server_socket"
    socket_paths = ["/tmp/server_socket_1", "/tmp/server_socket_2"]
    max_workers = 100
    cmd_args = getArgs()
    if cmd_args.ms:
        print("multi socket")
        api_service = ApiServiceMS([MyHandler], socket_paths, max_workers)
    else:
        print("single socket")
        api_service = ApiService([MyHandler], socket_path, max_workers)
    api_service.run(args)