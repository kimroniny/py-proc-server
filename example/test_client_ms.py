import threading
import sys
from loguru import logger
from client.client_ms import ClientMS

logger.remove()  # Remove the default logger
logger.add(sys.stderr, level="INFO")  # Set logger to only show INFO level logs

def get(client: ClientMS, url: str, params: dict):
    response = client.get(url, params)
    logger.info(f"收到响应: {response.code}, {response.msg}, {response.err}")
    return response

class ClientSimulator:
    def __init__(self, socket_paths, num_clients):
        self.socket_paths = socket_paths
        self.num_clients = num_clients

    def run(self):
        threads = []
        for i in range(self.num_clients):
            client = ClientMS(self.socket_paths)
            message = f"hello I am client {i}"
            params = {'msg': message}
            url = "/"
            # print(f"发送消息长度: {len(message)}")
            t = threading.Thread(target=get, args=(client, url, params))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

if __name__ == "__main__":
    socket_paths = ["/tmp/server_socket_1", "/tmp/server_socket_2"]
    num_clients = 20  # 模拟100个客户端
    simulator = ClientSimulator(socket_paths, num_clients)
    simulator.run()
