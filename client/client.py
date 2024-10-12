
from server.response import Response
from typing import Dict, Any
from loguru import logger
import time
import multiprocessing
import threading
from multiprocessing.connection import Client as MClient, Connection

class Client:
    def __init__(self, socket_path, reuse_client=False):
        self.socket_path = socket_path
        self.reuse_client = reuse_client
        self.__client = None
        if self.reuse_client:
            self.__client: Connection = MClient(self.socket_path)

    def get(self, url: str, params: Dict[str, Any]) -> Response:
        return self.send(url, "GET", params)

    def post(self, url: str, params: Dict[str, Any]) -> Response:
        return self.send(url, "POST", params)
    
    def send(self, url:str, method:str, params:Dict[str, Any]) -> Response:
        if not self.reuse_client:
            return self.__send_no_reuse(url, method, params)
        else:
            return self.__send_reuse(url, method, params)

    def __send_reuse(self, url: str, method: str, params: Dict[str, Any]) -> Response:
        message = {
            "method": method,
            "url": url,
            "params": params,
        }
        self.__client.send(message)
        response = self.__client.recv()
        response = Response.from_str(response)
        # print(f"收到服务器响应, code: {response.code}, msg: {response.msg}, err: {response.err}")
        return response
    
    def __close(self, client: Connection):
        try:
            fileno = client.fileno()
            logger.debug(f"client(fileno: {fileno}) send close message to server")
            client.send("close")
            ack = client.recv()
            assert str(ack).startswith("ok#")
            client.close()
            logger.debug(f"client(fileno: {fileno}) closed, recv from server: {ack}")
        except Exception as e:
            logger.error(f"Error closing client: {e}")

    def __send_no_reuse(self, url: str, method: str, params: Dict[str, Any]) -> Response:
        client: Connection = MClient(self.socket_path)
        logger.debug(f"process id: {multiprocessing.current_process().name}, thread id: {threading.current_thread().name}, object id: {id(self)}, create client fileno: {client.fileno()}")
        message = {
            "method": method,
            "url": url,
            "params": params,
        }
        client.send(message)
        response = client.recv()
        response = Response.from_str(response)
        self.__close(client)
        logger.debug(f"send request finish!")
        return response
    
    def __del__(self):
        if self.__client:
            self.__close(self.__client)
