import socket
import os
import threading
import queue
import select
import json
import struct
import asyncio
import signal
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor

@dataclass
class Message:
    type: str
    payload: Any
    client_id: Optional[str] = None

class FrameProtocol:
    """Protocol for framing messages with length prefix"""
    
    @staticmethod
    def pack(data: bytes) -> bytes:
        """Pack data with length prefix"""
        length = len(data)
        return struct.pack('!I', length) + data
    
    @staticmethod
    def unpack(sock: socket.socket) -> Optional[bytes]:
        """Read length-prefixed frame from socket"""
        try:
            # Read 4-byte length prefix
            length_data = sock.recv(4)
            if not length_data:
                return None
                
            length = struct.unpack('!I', length_data)[0]
            data = bytearray()
            
            # Read the full message
            while len(data) < length:
                chunk = sock.recv(min(length - len(data), 8192))
                if not chunk:
                    return None
                data.extend(chunk)
                
            return bytes(data)
        except socket.error:
            return None

class UnixDomainServer:
    """High-performance Unix Domain Socket Server"""
    
    def __init__(self, socket_path: str, num_workers: int = 4):
        self.socket_path = socket_path
        self.num_workers = num_workers
        self.clients: Dict[str, socket.socket] = {}
        self.handlers: Dict[str, Callable] = {}
        self.running = False
        self.worker_pool = ThreadPoolExecutor(max_workers=num_workers)
        self.message_queue = queue.Queue()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('UnixDomainServer')
        
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type"""
        self.handlers[message_type] = handler
        
    def _cleanup_socket(self):
        """Remove existing socket file if it exists"""
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            self.logger.error(f"Error cleaning up socket: {e}")
            
    def _handle_client(self, client_sock: socket.socket, client_id: str):
        """Handle individual client connection"""
        self.logger.info(f"New client connected: {client_id}")
        self.clients[client_id] = client_sock
        
        while self.running:
            try:
                # Read framed message
                data = FrameProtocol.unpack(client_sock)
                if not data:
                    break
                    
                # Parse message
                message = json.loads(data.decode())
                msg_type = message.get('type')
                
                if msg_type in self.handlers:
                    # Process message in worker pool
                    future = self.worker_pool.submit(
                        self.handlers[msg_type],
                        Message(
                            type=msg_type,
                            payload=message.get('payload'),
                            client_id=client_id
                        )
                    )
                    future.add_done_callback(
                        lambda f: self.message_queue.put((client_id, f.result()))
                    )
                    
            except (json.JSONDecodeError, struct.error) as e:
                self.logger.error(f"Protocol error from client {client_id}: {e}")
                break
            except Exception as e:
                self.logger.error(f"Error handling client {client_id}: {e}")
                break
                
        # Cleanup client
        self.clients.pop(client_id, None)
        client_sock.close()
        self.logger.info(f"Client disconnected: {client_id}")
        
    def _response_handler(self):
        """Handle responses to clients"""
        while self.running:
            try:
                client_id, response = self.message_queue.get(timeout=1)
                if client_id in self.clients:
                    client_sock = self.clients[client_id]
                    data = json.dumps(response).encode()
                    framed_data = FrameProtocol.pack(data)
                    client_sock.sendall(framed_data)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error sending response: {e}")
                
    def start(self):
        """Start the server"""
        self._cleanup_socket()
        self.running = True
        
        # Create Unix domain socket
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_sock.bind(self.socket_path)
            os.chmod(self.socket_path, 0o666)  # Allow broad access
            server_sock.listen(128)
            
            # Start response handler
            response_thread = threading.Thread(target=self._response_handler)
            response_thread.start()
            
            self.logger.info(f"Server started on {self.socket_path}")
            
            # Set up polling
            poll = select.poll()
            poll.register(server_sock.fileno(), select.POLLIN)
            
            while self.running:
                events = poll.poll(1000)  # 1 second timeout
                for fd, event in events:
                    if fd == server_sock.fileno():
                        client_sock, _ = server_sock.accept()
                        client_id = str(id(client_sock))
                        
                        # Set socket options
                        client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
                        client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
                        
                        # Start client handler thread
                        thread = threading.Thread(
                            target=self._handle_client,
                            args=(client_sock, client_id)
                        )
                        thread.start()
                        
        except Exception as e:
            self.logger.error(f"Server error: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the server"""
        self.running = False
        
        # Close all client connections
        for client_sock in self.clients.values():
            client_sock.close()
        self.clients.clear()
        
        # Cleanup
        self._cleanup_socket()
        self.worker_pool.shutdown()
        self.logger.info("Server stopped")

# Async version of the server
class AsyncUnixDomainServer:
    """Asynchronous Unix Domain Socket Server"""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.clients = {}
        self.handlers = {}
        self.running = False
        self.logger = logging.getLogger('AsyncUnixDomainServer')
        
    def register_handler(self, message_type: str, handler: Callable):
        """Register an async handler for a message type"""
        self.handlers[message_type] = handler
        
    async def _handle_client(self, reader: asyncio.StreamReader, 
                           writer: asyncio.StreamWriter, client_id: str):
        """Handle individual client connection"""
        self.logger.info(f"New client connected: {client_id}")
        self.clients[client_id] = writer
        
        try:
            while self.running:
                # Read length prefix
                length_data = await reader.readexactly(4)
                if not length_data:
                    break
                    
                length = struct.unpack('!I', length_data)[0]
                data = await reader.readexactly(length)
                
                # Parse message
                message = json.loads(data.decode())
                msg_type = message.get('type')
                
                if msg_type in self.handlers:
                    # Process message
                    response = await self.handlers[msg_type](
                        Message(
                            type=msg_type,
                            payload=message.get('payload'),
                            client_id=client_id
                        )
                    )
                    
                    # Send response
                    response_data = json.dumps(response).encode()
                    framed_data = FrameProtocol.pack(response_data)
                    writer.write(framed_data)
                    await writer.drain()
                    
        except (asyncio.IncompleteReadError, json.JSONDecodeError) as e:
            self.logger.error(f"Protocol error from client {client_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error handling client {client_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            self.clients.pop(client_id, None)
            self.logger.info(f"Client disconnected: {client_id}")
            
    async def start(self):
        """Start the async server"""
        self._cleanup_socket()
        self.running = True
        
        try:
            server = await asyncio.start_unix_server(
                lambda r, w: self._handle_client(
                    r, w, str(id(w))
                ),
                path=self.socket_path
            )
            
            os.chmod(self.socket_path, 0o666)
            self.logger.info(f"Async server started on {self.socket_path}")
            
            async with server:
                await server.serve_forever()
                
        except Exception as e:
            self.logger.error(f"Server error: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the async server"""
        self.running = False
        self._cleanup_socket()
        self.logger.info("Async server stopped")
        
    def _cleanup_socket(self):
        """Remove existing socket file"""
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            self.logger.error(f"Error cleaning up socket: {e}")