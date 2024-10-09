import socket
import threading
from multiprocessing.connection import Client as MClient, Connection

class Client:
    def __init__(self, socket_path):
        self.socket_path = socket_path

    def send_message(self, message):
        client: Connection = MClient(self.socket_path)
        client.send(message.encode())
        response = client.recv()
        print(f"收到服务器响应: {response.decode()}")
        client.close()

class ClientSimulator:
    def __init__(self, socket_path, num_clients):
        self.socket_path = socket_path
        self.num_clients = num_clients

    def run(self):
        threads = []
        for i in range(self.num_clients):
            client = Client(self.socket_path)
            message = f"来自客户端 {i} 的消息"*1024
            print(f"发送消息长度: {len(message)}")
            t = threading.Thread(target=client.send_message, args=(message,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

if __name__ == "__main__":
    socket_path = "/tmp/server_socket"
    num_clients = 1  # 模拟100个客户端
    simulator = ClientSimulator(socket_path, num_clients)
    simulator.run()