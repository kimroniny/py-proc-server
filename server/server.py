from __future__ import annotations
import os
import json
import sys
import traceback
import time
import threading
import multiprocessing
import traceback
import os
from loguru import logger
from typing import List, Tuple, Dict, Any, Optional
from multiprocessing.connection import Listener, Client, Connection
import signal
from concurrent.futures import ThreadPoolExecutor
from server.response import Response
from server.handler import Handler
from server.connection_storage import ConnectionStorage


Route = Tuple[str, Handler, Dict[str, Any]]

class Server:
    def __init__(self, routes: List[Route], max_workers: Optional[int]=None, max_conns: Optional[int]=None):
        self.routes_map: dict[str, Tuple[Handler, Dict[str, Any]]] = {url: (handler, args) for url, handler, args in routes}
        self.max_workers = max_workers or multiprocessing.cpu_count() * 2  # 设置线程池大小
        self.connection_storage = ConnectionStorage(max_size=max_conns or self.max_workers)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def __setup(self, socket_path: str, stop_event: threading.Event) -> bool:
        if os.path.exists(socket_path):
            logger.error(f"socket path {socket_path} already exists, remove it")
            return False
        self.server = Listener(family='AF_UNIX', address=socket_path)
        self.connection_storage.init_stop_flag(stop_event)
        logger.debug(f"服务器正在监听 {socket_path}")
        return True

    def __listen_accept(self, stop_event: threading.Event):
        try:
            while not stop_event.is_set():
                try:
                    c = self.server.accept()
                    logger.debug(f"accept connection: {c.fileno()}")
                except OSError:
                    continue
                ret = self.connection_storage.add(c)
                if ret == 1:
                    logger.warning("connection storage is closed, refuse and close the connection")
                    c.close()
                    continue
                elif ret == 2:
                    logger.warning("connection storage is full, refuse and close the connection")
                    c.close()
                    continue
                elif ret == 0:
                    continue
                else:
                    raise Exception(f"unknown return value when add connection storage: {ret}")
        except (KeyboardInterrupt, SystemExit):
            self.server.close()
            self.executor.shutdown(wait=True)  # 关闭线程池
        finally:
            stop_event.set()
            logger.info("服务器已关闭")
    
    def __poll_data(self, stop_event: threading.Event):
        thread_poll = threading.Thread(target=self.connection_storage.poll)
        thread_poll.start()
        try:
            while not stop_event.is_set():
                item: Optional[Tuple[Connection, Any]] = self.connection_storage.get_msg_from_available_conn_queue()
                if item:
                    self.executor.submit(self.__handle, item)
        except Exception as e:
            logger.error(f"Error in poll data: {traceback.format_exc()}")
            stop_event.set()

    def __handle(self, item: Tuple[Connection, Any]):
        try:
            conn, data = item
            logger.debug(f"recv data: {data}")

            if data == 'close':
                """
                方案1 "向客户端发送响应" 和 "删除并关闭服务端链接" 未绑定为原子操作
                由于"发送响应"和"删除并关闭服务端链接"未能保证原子性, 所以存在客户端已经关闭链接, 但是服务端链接还未删除并关闭的情况
                又因为客户端在关闭链接时会向服务端发送一个空消息, 就导致 ConnectionStorage 中的 poll() 会将该链接放入 available_conns 队列中
                然后服务端从 available_conns 中读取到这个空消息, 就会对该链接进行处理, 就会导致错误
                所以如果采用方案1, 就要在 ConnectionStorage 中需要对客户端关闭链接的情况进行特殊处理, 也就是捕获 EOFError 异常
                
                # fileno = conn.fileno()
                # conn.send(f"ok#fileno:{conn.fileno()}")
                # logger.info(f"ignore before connection closed(fileno: {fileno})!")
                # self.connection_storage.remove(conn)
                # logger.info(f"connection closed(fileno: {fileno})!")
                """

                """
                方案2 "向客户端发送响应" 和 "删除并关闭服务端链接" 绑定为原子操作
                由于二者已经绑定为原子操作, 所以客户端关闭连接时, 服务端也会删除并关闭链接
                此时, ConnectionStorage 中的 poll() 在遍历 storage 集合时, 不会遍历客户端已经关闭的链接
                """
                fileno = conn.fileno()
                self.connection_storage.close_and_remove(conn)
                logger.debug(f"connection closed(fileno: {fileno})!")
                return

            response = self.__process_data(data)
            resp_str = response.to_str()
            conn.send(resp_str)
            logger.debug(f"send response: {resp_str}")
        except Exception as e:
            logger.error(f"Error in handling connection: {traceback.format_exc()}")
        finally:
            # if conn and not conn.closed:
            #     conn.close()  # 确保连接在处理完后关闭
            pass
    
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
        
    def start(self, socket_path: str, stop_event: threading.Event):
        self.stop_event = stop_event
        
        if not self.__setup(socket_path, stop_event): return

        thread_poll_data = threading.Thread(target=self.__poll_data, args=(stop_event, ))
        thread_poll_data.start()

        thread_listen_accept = threading.Thread(target=self.__listen_accept, args=(stop_event, ))
        thread_listen_accept.start()

        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

        thread_poll_data.join()
        thread_listen_accept.join()
    
    def stop(self):
        if self.stop_event:
            self.stop_event.set()

if __name__ == "__main__":
    socket_path = "/tmp/server_socket"
    server = Server(20)
    stop_event = threading.Event()
    server.start(socket_path, stop_event)
