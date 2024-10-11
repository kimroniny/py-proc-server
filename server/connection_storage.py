import queue
import threading
import time
import traceback
from loguru import logger
from multiprocessing.connection import Connection
from typing import Dict, Set, Any, Tuple

class ConnectionStorage:
    def __init__(self, max_size: int=100):
        self.storage: Set[Connection] = set()
        self.max_size: int = max_size
        self.exist_in_queue: Dict[Connection, bool] = {}
        self.available_conns: queue.Queue = queue.Queue()
        self.stop_flag: threading.Event = None
        self.storage_lock = threading.RLock()
        self.__closed = False

    def add(self, conn: Connection) -> int:
        if self.__closed:
            return 1
        if len(self.storage) >= self.max_size:
            logger.warning(f"connection storage is full(size={len(self.storage)})")
            return 2
        with self.storage_lock:
            self.storage.add(conn)
            self.exist_in_queue[conn] = False
        return 0

    def remove(self, conn: Connection):
        with self.storage_lock:
            try:
                if conn not in self.storage:
                    return
                self.storage.remove(conn)
                del self.exist_in_queue[conn]
                if not conn.closed:
                    conn.close()
            except Exception as e:
                logger.error(f"Error removing and closing connection in ConnectionStorage: {e}")
        
    def init_stop_flag(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag

    def get_msg_from_available_conn_queue(self) -> Tuple[Connection, Any]:
        while True:
            conn: Connection = self.available_conns.get()
            with self.storage_lock:
                if conn in self.storage and not conn.closed:
                    print(f"connection is polled: {conn.poll()}, closed: {conn.closed}, fileno: {conn.fileno()}")
                    try:
                        msg = conn.recv()
                    # 从conn中接收完所有消息后, 才可以设置为 false, 此时 poll 线程才可以重新将 conn 加入到 available_conns 队列中
                        self.exist_in_queue[conn] = False 
                        return conn, msg
                    except Exception as e:
                        logger.error(f"Error receiving message from connection in ConnectionStorage: {traceback.format_exc()}; \n connection fileno: {conn.fileno()}")
                        self.remove(conn)

    def __close_conns(self):
        with self.storage_lock:
            try:
                for conn in self.storage:
                    conn.close()
                self.storage.clear()
            except Exception as e:
                logger.error(f"Error closing connection in ConnectionStorage: {e}")
            finally:
                self.__closed = True

    def poll(self):
        assert self.stop_flag is not None
        try:
            while not self.stop_flag.is_set():
                with self.storage_lock:
                    for conn in self.storage:
                        if not self.exist_in_queue.get(conn, False) and conn.poll(): # 先判断是否在队列中, 再判断是否可读
                            self.available_conns.put(conn)
                            self.exist_in_queue[conn] = True
                time.sleep(0)
        except Exception as e:
            logger.error(f"Error in poll: {traceback.format_exc()}")
        finally:
            self.__close_conns()
            self.stop_flag.set()