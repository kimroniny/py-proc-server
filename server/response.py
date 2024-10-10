from __future__ import annotations
import json

class Response:
    def __init__(self, code: int, msg: str='', err: str=''):
        self.code = code
        self.msg = msg
        self.err = err

    def to_str(self) -> str:
        return json.dumps(self.__dict__)

    @staticmethod
    def from_str(json_str: str) -> Response:
        return Response(**json.loads(json_str))