from __future__ import annotations
import asyncio
import threading
from typing import Dict
from server import Server, Handler

from typing import Dict


class StandardResponse(object):
    code: int = 199
    msg: str = ""
    error: str = ""

    def __init__(self) -> None:
        pass

    def set_code(self, code: int) -> StandardResponse:
        self.code = code
        return self

    def set_msg(self, msg: str) -> StandardResponse:
        self.msg = msg
        return self

    def set_error(self, err: str) -> StandardResponse:
        self.error = err
        return self

    def as_json(self) -> Dict:
        return {"code": self.code, "msg": self.msg, "error": self.error}

class MyHandler(Handler):
    @classmethod
    def routers(cls) -> Dict[str, str]:
        return {
            r'/': cls.hello,
        }

    def get(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_json())

    def hello(self):
        self.write('hello')

class ApiService(object):
    def __init__(self) -> None:
        self.stop_event: asyncio.Event = None

    def make_server(self, args: Dict = None) -> Server:
        if args is None:
            args = {}
        handlers = [
            MyHandler,
        ]
        routes = []
        for handler in handlers:
            routes += [(route, handler, args) for route in handler.routers().keys()]
        return Server(routes)

    async def run_app(self, args: Dict = None):
        if args is None:
            args = {}
        server = self.make_server(args)
        socket_path = args.get("socket_path", "/tmp/server_socket")
        server_thread = threading.Thread(target=server.listen, args=(socket_path,))
        server_thread.daemon = True
        server_thread.start()
        print(f"api service({socket_path}) is listening...")
        self.stop_event = asyncio.Event()
        try:
            await self.stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        print(f"api service({socket_path}) stopped!")

    def stop(self) -> None:
        assert self.stop_event is not None
        self.stop_event.set()

    def run(self, args: Dict) -> None:
        asyncio.run(self.run_app(args))

if __name__ == "__main__":
    args = {
        "socket_path": "/tmp/server_socket",
    }
    api_service = ApiService()
    api_service.run(args)