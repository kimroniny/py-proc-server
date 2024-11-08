import asyncio
import time
import json
import threading
import socket
from concurrent.futures import ThreadPoolExecutor
from server_async.server_async import UnixDomainServer, Message, FrameProtocol, AsyncUnixDomainServer

# Example usage of synchronous server
def example_sync_server():
    server = UnixDomainServer('/tmp/ipc_test.sock', num_workers=30)
    
    # Register message handlers
    def handle_echo(message: Message):
        return {
            'status': 'ok',
            'echo': message.payload
        }
        
    def handle_compute(message: Message):
        # Simulate CPU-intensive task
        time.sleep(0.1)
        return {
            'status': 'ok',
            'result': sum(range(message.payload))
        }
    
    server.register_handler('echo', handle_echo)
    server.register_handler('compute', handle_compute)
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.start)
    server_thread.start()
    
    return server, server_thread

# Example usage of async server
def example_async_server():
    server = AsyncUnixDomainServer('/tmp/ipc_test.sock')
    
    # Register async message handlers
    async def handle_echo(message: Message):
        return {
            'status': 'ok',
            'echo': message.payload
        }
        
    async def handle_compute(message: Message):
        # Simulate CPU-intensive task
        await asyncio.sleep(0.1)
        return {
            'status': 'ok',
            'result': sum(range(message.payload))
        }
    
    server.register_handler('echo', handle_echo)
    server.register_handler('compute', handle_compute)
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=asyncio.run, args=(server.start(),))
    server_thread.start()
    
    return server, server_thread

# Example client code
def create_client(path):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(path)
    return sock

def send_message(sock, message_type, payload):
    message = {
        'type': message_type,
        'payload': payload
    }
    data = json.dumps(message).encode()
    framed_data = FrameProtocol.pack(data)
    sock.sendall(framed_data)
    
    # Read response
    response_data = FrameProtocol.unpack(sock)
    if response_data:
        return json.loads(response_data.decode())
    return None

# Example benchmark
def run_benchmark():
    # server, server_thread = example_sync_server()
    server, server_thread = example_async_server()
    time.sleep(1)  # Wait for server to start
    
    # Create multiple clients
    num_clients = 2
    num_messages = 2
    clients = [create_client('/tmp/ipc_test.sock') for _ in range(num_clients)]
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max(num_clients, 30)) as executor:
        def client_task(client):
            for _ in range(num_messages):
                response = send_message(client, 'echo', 'test message')
                assert response['status'] == 'ok'
                
        # Run all clients concurrently
        futures = [executor.submit(client_task, client) for client in clients]
        for future in futures:
            future.result()
            
    end_time = time.time()
    total_messages = num_clients * num_messages
    duration = end_time - start_time
    msgs_per_sec = total_messages / duration
    
    print(f"Processed {total_messages} messages in {duration:.2f} seconds")
    print(f"Throughput: {msgs_per_sec:.2f} messages/second")
    
    # Cleanup
    for client in clients:
        client.close()
    server.stop()
    server_thread.join()

if __name__ == '__main__':
    run_benchmark()