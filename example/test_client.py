import threading
from client.client import Client

def get(client: Client, url: str, params: dict):
    response = client.get(url, params)
    print(f"收到响应: {response.code}, {response.msg}, {response.err}")
    return response

class ClientSimulator:
    def __init__(self, socket_path, num_clients):
        self.socket_path = socket_path
        self.num_clients = num_clients

    def run(self):
        threads = []
        for i in range(self.num_clients):
            client = Client(self.socket_path)
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
    socket_path = "/tmp/server_socket"
    num_clients = 100  # 模拟100个客户端
    simulator = ClientSimulator(socket_path, num_clients)
    simulator.run()