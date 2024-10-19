import queue
import threading
import time
import traceback
import math
import select
from typing import List
from concurrent.futures import ThreadPoolExecutor, wait as wait_futures
from selectors import SelectSelector, EVENT_READ, EpollSelector
from loguru import logger
from multiprocessing.connection import Connection, wait
from typing import Dict, Set, Any, Tuple, Optional

class ConnectionStorage:
    def __init__(self, max_size: Optional[int]=None):
        self.storage: Set[Connection] = set()
        self.max_size: Optional[int] = max_size
        self.exist_in_queue: Dict[Connection, bool] = {}
        self.available_conns: queue.Queue = queue.Queue()
        self.stop_flag: threading.Event = None
        self.storage_lock = threading.RLock()
        self.__closed = False
        # self._selector: Optional[SelectSelector] = EpollSelector()
        self._selector: Optional[SelectSelector] = SelectSelector()
        self._executor_recv_msgs = ThreadPoolExecutor()

    def add(self, conn: Connection) -> int:
        if self.__closed:
            return 1
        if self.max_size is not None and len(self.storage) >= self.max_size:
            logger.warning(f"connection storage is full(size={len(self.storage)})")
            return 2
        with self.storage_lock:
            self.storage.add(conn)
            self._selector.register(conn, EVENT_READ)
            self.exist_in_queue[conn] = False
        return 0

    def _remove_conn(self, conn: Connection):
        self.storage.remove(conn)
        self._selector.unregister(conn)
        del self.exist_in_queue[conn]
        if not conn.closed:
            conn.close()

    def remove(self, conn: Connection):
        with self.storage_lock:
            try:
                if conn not in self.storage:
                    return
                self._remove_conn(conn)
            except Exception as e:
                logger.error(f"Error removing and closing connection in ConnectionStorage: {e}")

    def close_and_remove(self, conn: Connection):
        with self.storage_lock:
            try:
                if conn not in self.storage:
                    return
                conn.send(f"ok#fileno:{conn.fileno()}")
                self._remove_conn(conn)
            except Exception as e:
                logger.error(f"Error removing and closing connection in ConnectionStorage: {e}")
        
    def init_stop_flag(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag

    def get_msg_from_available_conn_queue2(self, timeout: float=0.01) -> Optional[Tuple[Connection, Any]]:
        """
        在连接数大于500时, 使用该方法效果不行, 在连接数小于500时, 效果还可以, 和下面的方法相比, 相差很小
        """
        while not self.stop_flag.is_set():
            try:
                conn: Connection = self.available_conns.get(timeout=timeout)
            except queue.Empty:
                return None

            with self.storage_lock:
                if conn in self.storage and not conn.closed:
                    logger.debug(f"connection is polled: {conn.poll()}, available obj: {wait([conn])}, closed: {conn.closed}, fileno: {conn.fileno()}")
                    try:
                        logger.debug("waiting recv...")
                        msg = conn.recv()
                        # 从conn中接收完所有消息后, 才可以设置为 false, 此时 poll 线程才可以重新将 conn 加入到 available_conns 队列中
                        self.exist_in_queue[conn] = False 
                        logger.debug(f"recv msg: {msg} from connection(fileno: {conn.fileno()}), conn: {conn}, conn.poll: {conn.poll()}")
                        return conn, msg
                    except EOFError:
                        # 客户端关闭连接时, conn.poll() 也会收到通知, 但是消息为空, 此时只能通过捕获 EOFError 异常来判断
                        logger.warning(f"EOFError receiving message from connection(fileno: {conn.fileno()}) in ConnectionStorage")
                        self.remove(conn)
                    except Exception as e:
                        logger.error(f"Error receiving message from connection(fileno: {conn.fileno()}) in ConnectionStorage: {traceback.format_exc()}")
                        self.remove(conn)
                else:
                    continue
        return None

    def get_msg_from_available_conn_queue(self, timeout: float=0.01) -> Optional[Tuple[Connection, Any]]:
        """
        适用于大规模连接的情况, 在连接数大于500时, 效果比 get_msg_from_available_conn_queue2 好
        但是优势有限, 仅10%左右
        而且后面考虑用 epoll 来实现, 因为 select 有 fd 数量限制, 而且每次都要遍历所有 fd
        """
        def _try_remove_conn(conn: Connection):
            try:
                self._remove_conn(conn)
            except Exception as e:
                logger.error(f"Error removing and closing connection when getting it from queue: {traceback.format_exc()}")

        def recv_msgs_from_conns(conn: Connection):
            if conn in self.storage and not conn.closed:
                logger.debug(f"connection is polled: {conn.poll()}, available obj: {wait([conn])}, closed: {conn.closed}, fileno: {conn.fileno()}")
                try:
                    logger.debug("waiting recv...")
                    msgs = []
                    msg = conn.recv()
                    msgs.append(msg)
                    # limit = 20 # 每次最多接收20条消息, 减少阻塞时间
                    limit = 20
                    while True:
                        if len(msgs) >= limit:
                            break
                        
                        # 方案 1: 使用 select 去筛选
                        r, _, _ = select.select([conn], [], [], 0.001)
                        if r:
                            msg = conn.recv()
                            msgs.append(msg)
                            logger.debug(f"recv msg: {msg} from connection(fileno: {conn.fileno()}), conn: {conn}, conn.poll: {conn.poll()}")
                        else:
                            break

                        # # 方案2: 尝试 recv()
                        # try:
                        #     msg = conn.recv()
                        #     msgs.append(msg)
                        #     logger.debug(f"recv msg: {msg} from connection(fileno: {conn.fileno()}), conn: {conn}, conn.poll: {conn.poll()}")
                        # except EOFError:
                        #     break

                    # 从conn中接收完所有消息后, 才可以设置为 false, 此时 poll 线程才可以重新将 conn 加入到 available_conns 队列中
                    self.exist_in_queue[conn] = False 
                    logger.debug(f"recv msg(total {len(msgs)}) from connection(fileno: {conn.fileno()}), conn: {conn}, conn.poll: {conn.poll()}")
                    return conn, msgs
                except EOFError:
                    # 客户端关闭连接时, conn.poll() 也会收到通知, 但是消息为空, 此时只能通过捕获 EOFError 异常来判断
                    logger.warning(f"EOFError receiving message from connection(fileno: {conn.fileno()}) in ConnectionStorage")
                    # self.remove(conn)
                    _try_remove_conn(conn)
                    return None
                except Exception as e:
                    logger.error(f"Error receiving message from connection(fileno: {conn.fileno()}) in ConnectionStorage: {traceback.format_exc()}")
                    # self.remove(conn)
                    _try_remove_conn(conn)
                    return None
            else:
                return None
                        

        conns = []
        qsize = self.available_conns.qsize()
        # limit = math.ceil(math.sqrt(qsize))
        limit = qsize
        for i in range(limit):
            try:
                # 其实这里不用写 try, 因为只有一个线程在取, 不会出现多个线程同时取的情况, 而且 sqrt <= qsize 保证了不会阻塞
                conn = self.available_conns.get(timeout=timeout)
                conns.append(conn)
            except queue.Empty:
                break
        
        if len(conns) == 0: return None
        
        with self.storage_lock:
            # 在锁释放前必须要等待各个子线程执行完成
            results = list(self._executor_recv_msgs.map(recv_msgs_from_conns, conns, timeout=30))
        
        return results

    def poll(self):
        assert self.stop_flag is not None
        try:
            while not self.stop_flag.is_set():
                with self.storage_lock:
                    ready = self._selector.select(timeout=0.01) # 阻塞, 直到有连接可读
                    for key, events in ready:
                        conn = key.fileobj
                        if not self.exist_in_queue.get(conn, False):
                            logger.debug(f"connection is polled: {conn.poll()}, fileno: {conn.fileno()}, exist in queue: {self.exist_in_queue}")
                            self.available_conns.put(conn)
                            self.exist_in_queue[conn] = True
                time.sleep(0)
        except Exception as e:
            logger.error(f"Error in poll: {traceback.format_exc()}")
        finally:
            self.__close_conns()
            self.__close_selector()
            self.__close_executor()
            self.stop_flag.set()
    
    def poll2(self):
        # 这种方式太低效了, 不采用
        assert self.stop_flag is not None
        try:
            while not self.stop_flag.is_set():
                with self.storage_lock:
                    for conn in self.storage:
                        if not self.exist_in_queue.get(conn, False) and conn.poll(): # 先判断是否在队列中, 再判断是否可读
                            logger.debug(f"connection is polled: {conn.poll()}, fileno: {conn.fileno()}, exist in queue: {self.exist_in_queue}")
                            self.available_conns.put(conn)
                            self.exist_in_queue[conn] = True
                time.sleep(0)
        except Exception as e:
            logger.error(f"Error in poll: {traceback.format_exc()}")
        finally:
            self.__close_conns()
            self.stop_flag.set()
    
    

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

    def __close_selector(self):
        if self._selector is not None:
            self._selector.close()
            self._selector = None

    def __close_executor(self):
        if self._executor_recv_msgs is not None:
            self._executor_recv_msgs.shutdown(wait=False)
            self._executor_recv_msgs = None
