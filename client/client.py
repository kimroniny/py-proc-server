
from server.response import Response
from typing import Dict, Any
from multiprocessing.connection import Client as MClient, Connection

class Client:
    def __init__(self, socket_path):
        self.socket_path = socket_path

    def get(self, url: str, params: Dict[str, Any]) -> Response:
        return self.send(url, "GET", params)

    def post(self, url: str, params: Dict[str, Any]) -> Response:
        return self.send(url, "POST", params)

    def send(self, url: str, method: str, params: Dict[str, Any]) -> Response:
        client: Connection = MClient(self.socket_path)
        message = {
            "method": method,
            "url": url,
            "params": params,
        }
        client.send(message)
        response = client.recv()
        response = Response.from_str(response)
        # print(f"收到服务器响应, code: {response.code}, msg: {response.msg}, err: {response.err}")
        client.close()
        return response