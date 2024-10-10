from __future__ import annotations
import os
import json
import sys
import threading
import multiprocessing
import atexit
import os
from loguru import logger
from typing import List, Tuple, Dict, Any, TypeAlias, Optional
from multiprocessing.connection import Listener, Client, Connection
import signal
from concurrent.futures import ThreadPoolExecutor
from server.response import Response
from server.handler import Handler



Route: TypeAlias = Tuple[str, Handler, Dict[str, Any]]

class Server:
    def __init__(self, routes: List[Route], max_workers: Optional[int]=None):
        self.routes_map: dict[str, Tuple[Handler, Dict[str, Any]]] = {url: (handler, args) for url, handler, args in routes}
        self.max_workers = max_workers or multiprocessing.cpu_count() * 2  # 设置线程池大小
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def setup(self, socket_path: str) -> bool:
        if os.path.exists(socket_path):
            logger.error(f"socket path {socket_path} already exists, remove it")
            return False
        self.server = Listener(family='AF_UNIX', address=socket_path)
        logger.info(f"服务器正在监听 {socket_path}")
        return True

    def listen(self, socket_path: str, stop_event: threading.Event):
        try:
            if not self.setup(socket_path): return
            while not stop_event.is_set():
                try:
                    c = self.server.accept()
                except OSError:
                    continue
                self.executor.submit(self.__handle, c)
        except (KeyboardInterrupt, SystemExit):
            self.server.close()
            self.executor.shutdown(wait=True)  # 关闭线程池
        finally:
            stop_event.set()
            logger.info("服务器已关闭")

    def __handle(self, conn: Connection):
        try:
            data = conn.recv()
            logger.debug(f"recv data: {data}")
            response = self.__process_data(data)
            resp_str = response.to_str()
            conn.send(resp_str)
            logger.debug(f"send response: {resp_str}")
        except Exception as e:
            logger.error(f"Error in handling connection: {e}")
        finally:
            if conn and not conn.closed:
                conn.close()  # 确保连接在处理完后关闭
    
    def __process_data(self, data) -> Response:
        resp = Response(404)
        handler = None
        try:
            method = data.get('method')
            url = data.get('url')
            params = data.get('params', {})
            Handler, args = self.routes_map[url]
            handler = Handler(url=url, method=method, arguments=params)
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
            logger.error(f"process data error: {e}")
        finally:
            logger.debug(f"process data return before del: {resp}")
            if handler:
                del handler
            logger.debug(f"process data return: {resp}")
            return resp

if __name__ == "__main__":
    socket_path = "/tmp/server_socket"
    server = Server()
    server.listen(socket_path)