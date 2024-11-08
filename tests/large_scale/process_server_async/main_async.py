import asyncio
import time
import socket
import json
import statistics
import numpy as np
import struct
import asyncio
from dataclasses import dataclass
from typing import List, Dict
from server_async.server_async import Message, FrameProtocol, AsyncUnixDomainServer


@dataclass
class BenchmarkResult:
    messages_per_second: float
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_messages: int
    duration_seconds: float
    error_count: int

class AsyncClient:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.reader = None
        self.writer = None
        
    async def connect(self):
        self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
        
    async def send_message(self, message_type: str, payload: any) -> dict:
        message = {
            'type': message_type,
            'payload': payload
        }
        data = json.dumps(message).encode()
        framed_data = FrameProtocol.pack(data)
        
        self.writer.write(framed_data)
        await self.writer.drain()
        
        # Read response
        length_data = await self.reader.readexactly(4)
        length = struct.unpack('!I', length_data)[0]
        data = await self.reader.readexactly(length)
        
        return json.loads(data.decode())
        
    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

async def run_async_benchmark(
    socket_path: str,
    num_clients: int = 100,
    messages_per_client: int = 1000,
    payload_size: int = 100
):
    """Run benchmark for AsyncUnixDomainServer"""
    
    # Start server
    server = AsyncUnixDomainServer(socket_path)
    
    # Register handlers
    async def handle_echo(message: Message):
        return {
            'status': 'ok',
            'echo': message.payload
        }
    
    async def handle_compute(message: Message):
        result = sum(range(len(message.payload)))
        return {
            'status': 'ok',
            'result': result
        }
    
    server.register_handler('echo', handle_echo)
    server.register_handler('compute', handle_compute)
    
    # Start server in background task
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)  # Wait for server to start
    
    # Create test payload
    payload = 'x' * payload_size
    
    # Initialize clients
    clients = []
    for _ in range(num_clients):
        client = AsyncClient(socket_path)
        await client.connect()
        clients.append(client)
    
    # Prepare result storage
    latencies = []
    error_count = 0
    
    async def client_task(client: AsyncClient):
        nonlocal error_count
        client_latencies = []
        
        for _ in range(messages_per_client):
            try:
                start_time = time.perf_counter()
                response = await client.send_message('echo', payload)
                end_time = time.perf_counter()
                
                if response['status'] == 'ok':
                    latency = (end_time - start_time) * 1000  # Convert to ms
                    client_latencies.append(latency)
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                
        return client_latencies
    
    # Run benchmark
    print(f"Starting async benchmark with {num_clients} clients, {messages_per_client} messages each...")
    start_time = time.perf_counter()
    
    # Create tasks for all clients
    tasks = [client_task(client) for client in clients]
    results = await asyncio.gather(*tasks)
    
    # Flatten results
    latencies = [lat for client_lats in results for lat in client_lats]
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    # Calculate statistics
    total_messages = num_clients * messages_per_client - error_count
    messages_per_second = total_messages / duration
    avg_latency = statistics.mean(latencies)
    p95_latency = np.percentile(latencies, 95)
    p99_latency = np.percentile(latencies, 99)
    
    # Cleanup
    for client in clients:
        await client.close()
    server.stop()
    try:
        await asyncio.wait_for(server_task, timeout=1)
    except asyncio.TimeoutError:
        pass
    
    return BenchmarkResult(
        messages_per_second=messages_per_second,
        average_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        p99_latency_ms=p99_latency,
        total_messages=total_messages,
        duration_seconds=duration,
        error_count=error_count
    )

async def compare_benchmarks():
    """Run benchmarks comparing sync and async servers"""
    
    # Test configurations
    configs = [
        {'num_clients': 2, 'messages_per_client': 2},
        # {'num_clients': 50, 'messages_per_client': 1000},
        # {'num_clients': 100, 'messages_per_client': 1000},
    ]
    
    payload_sizes = [100, 1000, 10000]  # bytes
    
    results = []
    
    for config in configs:
        for size in payload_sizes:
            print(f"\nBenchmarking with {config['num_clients']} clients, "
                  f"{config['messages_per_client']} messages, "
                  f"{size} bytes payload")
            
            result = await run_async_benchmark(
                '/tmp/ipc_test_async.sock',
                num_clients=config['num_clients'],
                messages_per_client=config['messages_per_client'],
                payload_size=size
            )
            
            print(f"Results:")
            print(f"  Throughput: {result.messages_per_second:.2f} msgs/sec")
            print(f"  Average latency: {result.average_latency_ms:.2f} ms")
            print(f"  P95 latency: {result.p95_latency_ms:.2f} ms")
            print(f"  P99 latency: {result.p99_latency_ms:.2f} ms")
            print(f"  Errors: {result.error_count}")
            
            results.append({
                'num_clients': config['num_clients'],
                'messages_per_client': config['messages_per_client'],
                'payload_size': size,
                'result': result
            })
            
    return results

def plot_benchmark_results(results: List[Dict]):
    """Plot benchmark results using ASCII art"""
    print("\nBenchmark Summary (Throughput in msgs/sec)")
    print("==========================================")
    
    # Group results by payload size
    by_payload = {}
    for r in results:
        size = r['payload_size']
        if size not in by_payload:
            by_payload[size] = []
        by_payload[size].append(r)
    
    for size, size_results in sorted(by_payload.items()):
        print(f"\nPayload size: {size} bytes")
        print("Clients  Throughput  Avg Latency")
        print("--------------------------------")
        for r in sorted(size_results, key=lambda x: x['num_clients']):
            result = r['result']
            print(f"{r['num_clients']:7d} {result.messages_per_second:10.0f} {result.average_latency_ms:11.2f}ms")

if __name__ == '__main__':
    print("Running async IPC server benchmarks...")
    asyncio.run(compare_benchmarks())