from __future__ import annotations
import os
import json
import sys
import threading
import multiprocessing
import atexit
import os
from typing import List, Tuple, Dict, Any, TypeAlias
from multiprocessing.connection import Listener, Client, Connection
import signal
from concurrent.futures import ThreadPoolExecutor

class Response:
    def __init__(self, code: int, msg: str='', err: str=''):
        self.code = code
        self.msg = msg
        self.err = err

    def to_str(self) -> str:
        return json.dumps(self.__dict__)

    @staticmethod
    def from_str(json_str: str) -> Response:
        return Response(**json.loads(json_str))

ResponseContent: TypeAlias = str | bytes

class Handler:
    def __init__(self, arguments: Dict[str, Any]):
        self.__arguments = arguments
        self.__output = ""

    def get_argument(self, key: str) -> Any:
        return self.__arguments.get(key)
    
    def get_arguments(self, key: str) -> List[Any]:
        return self.__arguments.get(key, [])

    def get_output(self) -> ResponseContent:
        return self.__output
    
    def write(self, content: ResponseContent):
        self.__output = content

    def initialize(self, *args, **kwargs):
        pass

    def get(self):
        pass

    def post(self):
        pass
    

Route: TypeAlias = Tuple[str, Handler, Dict[str, Any]]

class Server:
    def __init__(self, routes: List[Route], max_workers=None):
        self.routes_map: dict[str, Tuple[Handler, Dict[str, Any]]] = {uri: (handler, args) for uri, handler, args in routes}
        self.max_workers = max_workers or multiprocessing.cpu_count() * 2  # 设置线程池大小
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def setup(self, socket_path: str):
        self.server = Listener(family='AF_UNIX', address=socket_path)
        print(f"服务器正在监听 {socket_path}")

    def listen(self, socket_path: str):
        self.setup(socket_path)
        try:
            while True:
                try:
                    c = self.server.accept()
                except OSError:
                    continue
                self.executor.submit(self.__handle, c)
        except (KeyboardInterrupt, SystemExit):
            self.server.close()
            self.executor.shutdown(wait=True)  # 关闭线程池
        finally:
            print("服务器已关闭")
            sys.exit(0)

    def __handle(self, conn: Connection):
        data = conn.recv()
        response = self.__process_data(data)
        conn.send(response.to_str().encode())
        conn.close()
    
    def __process_data(self, data) -> Response:
        resp = Response(404)
        try:
            method = data.get('method')
            uri = data.get('uri')
            params = data.get('params', {})
            handler, args = self.routes_map[uri]
            handler = handler(arguments=params)
            handler.initialize(*args)
            if method == 'GET':
                handler.get()
            elif method == 'POST':
                handler.post()
            else:
                raise Exception(f'Unsupported method: {method}')
            resp.code = 200
            resp.msg = handler.get_output()
        except Exception as e:
            resp.code = 500
            resp.err = str(e)
        finally:
            del handler
            return resp

if __name__ == "__main__":
    socket_path = "/tmp/server_socket"
    server = Server()
    server.listen(socket_path)