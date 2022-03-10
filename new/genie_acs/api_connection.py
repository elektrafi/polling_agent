#!/usr/bin/env python3
from types import new_class
from enum import Enum, unique
from typing import Mapping
import requests
from requests.exceptions import JSONDecodeError
from functools import partial


def create_deep_object(name: str, data: dict | str | list) -> object:
    if isinstance(data, Mapping):
        cls = new_class(name)()
        keys = data.keys()
        for k in keys:
            prefix = ""
            if k[0].isnumeric():
                prefix = "item"
            cls.__dict__[f"{prefix}{k}"] = create_deep_object(k, data[k])
        return cls
    return data


@unique
class GenieEndpoint(Enum):
    DEVICES = "devices"
    TASKS = "tasks"
    FAULTS = "faults"
    PRESETS = "presets"
    FILES = "files"
    PROVISIONS = "provisions"


class GenieACS:
    def __init__(
        self,
        host: str = "10.0.44.21",
        port: int = 7557,
        username: str = "admin",
        password: str = "password",
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self.apiUrl = f"http://{self._host}:{self._port}"
        self.session = requests.session()
        self.session.auth = (self._username, self._password)
        self.session.verify = False
        self._root_hook = partial(create_deep_object, "Device")

    def __del__(self):
        self.session.close()

    def get_api_url(self, ep: GenieEndpoint):
        return f"http://{self._host}:{self._port}/{ep.value}"

    def get_devices(self) -> list[object]:
        resp = self.session.get(self.get_api_url(GenieEndpoint.DEVICES))
        if resp is None or resp.status_code != 200:
            return []
        try:
            data = resp.json(object_hook=self._root_hook)
        except:
            raise JSONDecodeError
        return data
