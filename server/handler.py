from __future__ import annotations
from typing import List, Dict, Any, TypeAlias
from server.response import Response
from abc import ABC, abstractmethod
ResponseContent: TypeAlias = str | bytes

class Handler(ABC):
    def __init__(self, url: str, method: str, arguments: Dict[str, Any]):
        self.__url = url
        self.__method = method
        self.__arguments = arguments
        self.__output = ""

    def get_url(self) -> str:
        return self.__url

    def get_method(self) -> str:
        return self.__method

    def get_argument(self, key: str) -> Any:
        return self.__arguments.get(key)
    
    def get_arguments(self, key: str) -> List[Any]:
        return self.__arguments.get(key, [])

    def get_output(self) -> ResponseContent:
        return self.__output
    
    def write(self, content: ResponseContent):
        assert isinstance(content, ResponseContent)
        self.__output = content

    def initialize(self, *args, **kwargs):
        pass

    @abstractmethod
    def get(self):
        raise NotImplementedError

    @abstractmethod
    def post(self):
        raise NotImplementedError
