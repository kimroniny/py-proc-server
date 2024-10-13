from __future__ import annotations
import time
from typing import Dict 
from server.server import Handler
from loguru import logger
from service.api_service import ApiService
from service.api_service_ms import ApiService as ApiServiceMS
from example.application_response import StandardResponse
import argparse

class CalcHandler(Handler):
    @classmethod
    def routers(cls) -> Dict[str, str]:
        return {
            r'/': cls.hello,
            r'/calc': cls.calc,
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
        return f'server recv msg: {msg}'
    
    def calc(self):
        target = self.get_argument('target')
        cnt = 0
        start = time.time()
        for i in range(target):
            cnt += 1
        end = time.time()
        return f'{(end - start)*1000:.2f}ms'

def getArgs():
    parser = argparse.ArgumentParser(description="api service")
    parser.add_argument("--ms", action="store_true", help="multi socket")
    return parser.parse_args()

if __name__ == "__main__":
    args = {}
    socket_path = "/tmp/server_socket"
    MULTI_SOCKET_NUM = 2
    socket_paths = [f"/tmp/server_socket_{i}" for i in range(MULTI_SOCKET_NUM)]
    max_workers = 100
    cmd_args = getArgs()
    if cmd_args.ms:
        print("multi socket")
        api_service = ApiServiceMS([CalcHandler], socket_paths, max_workers)
    else:
        print("single socket")
        api_service = ApiService([CalcHandler], socket_path, max_workers)
    api_service.run(args)
