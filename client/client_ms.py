import random
import time
from server.response import Response
from typing import Dict, Any, List
from loguru import logger
from client.client import Client

class ClientMS:
    def __init__(self, socket_paths: List[str]):
        self.socket_paths = socket_paths
        self.__clients: List[Client] = [Client(socket_path) for socket_path in self.socket_paths]

    def get(self, url: str, params: Dict[str, Any]) -> Response:
        return self.send(url, "GET", params)

    def post(self, url: str, params: Dict[str, Any]) -> Response:
        return self.send(url, "POST", params)
    
    @property
    def __current_client(self) -> Client:
        return random.choice(self.__clients)

    def send(self, url: str, method: str, params: Dict[str, Any]) -> Response:
        return self.__current_client.send(url, method, params)
    
    # def __del__(self):
    #     print("close all clients before")
    #     start = time.time()
    #     for client in self.__clients:
    #         self.__close(client)
    #     end = time.time()
    #     logger.info(f"close all clients cost: {end - start}s")
