"""
本api适用于多线程和多进程架构, 但是不适用于异步架构

架构是指 api 和 bc 之间的存在关系
"""
import asyncio
import tornado.web
import time
import threading
from loguru import logger
from typing import Dict
from example.api_service import MyHandler
from example.application_response import StandardResponse

class MyAsyncHandler(tornado.web.RequestHandler):

    def initialize(self, *args, **kwargs):
        pass

    @classmethod
    def routers(cls) -> Dict[str, str]:
        return {
            r'/async': cls.hello,
        }

    def __get_func(self) -> callable:
        path = self.request.path
        routers = self.routers()
        callfunc = routers.get(path, None)
        if callfunc is None:
            raise Exception("invalid uri:'{}'".format(path))
        return callfunc

    async def get(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = await callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    async def hello(self):
        start = time.time()
        target = self.get_argument('msg')
        # print(f"recv msg in handler: {msg}")
        # await asyncio.sleep(1)
        cnt = 0
        for i in range(int(target)):
            cnt += 1
        end = time.time()
        return f'{(end - start)*1000:.2f}ms'

class MySyncHandler(tornado.web.RequestHandler):

    def initialize(self, *args, **kwargs):
        pass

    @classmethod
    def routers(cls) -> Dict[str, str]:
        return {
            r'/sync': cls.hello,
        }

    def __get_func(self) -> callable:
        path = self.request.path
        routers = self.routers()
        callfunc = routers.get(path, None)
        if callfunc is None:
            raise Exception("invalid uri:'{}'".format(path))
        return callfunc

    def get(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    def hello(self):
        msg = self.get_argument('msg')
        # print(f"recv msg in handler: {msg}")
        time.sleep(1)
        return f'server recv msg: {msg}'

class ApiService(object):
    def __init__(self) -> None:
        # 退出信号, 在多线程编程的场景下，不要用asyncio.Event，因为不同thread下的asyncio.Event是独立的, 无法跨线程通信
        self.stop_event: threading.Event = threading.Event() 

    def make_app(self, args: Dict = None) -> tornado.web.Application:
        if args is None:
            args = {}
        handlers = [
            MyAsyncHandler,
            MySyncHandler,
        ]
        routes = []
        for handler in handlers:
            routes += [(route, handler, args) for route in handler.routers().keys()]
        return tornado.web.Application(routes)

    async def run_app(self, args: Dict = None):
        if args is None:
            args = {}
        app = self.make_app(args)
        port = args.get("port", 8888)
        server = app.listen(port=port)
        logger.debug(f"api service({port}) is listening...")
        while not self.stop_event.is_set(): # 等待退出信号
            await asyncio.sleep(1)
        server.stop()
        logger.debug(f"api service({port}) stopped!")

    def stop(self) -> None:
        assert self.stop_event is not None
        self.stop_event.set()

    def run(self, args: Dict = None) -> None:
        asyncio.run(self.run_app(args))

if __name__ == "__main__":
    api_service = ApiService()
    api_service.run()

