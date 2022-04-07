#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from enum import Enum as _Enum, unique as _unique
import json as _json
import requests as _requests
from requests.exceptions import JSONDecodeError as _JSONDecodeError
from .device import device_object_hook as _device_object_hook
import logging as _logging
from typing_extensions import Self as _Self


@_unique
class GenieEndpoint(_Enum):
    DEVICES = "devices"
    TASKS = "tasks"
    FAULTS = "faults"
    PRESETS = "presets"
    FILES = "files"
    PROVISIONS = "provisions"


class GenieACS:
    _logger = _logging.getLogger(__name__)
    _host: str
    _port: int
    _username: str
    _password: str
    _apiUrl: str
    _session: _requests.Session
    _inst: _Self | None = None

    def __init__(
        self,
        host: str = "10.244.1.21",
        port: int = 7557,
        username: str = "admin",
        password: str = "password",
    ):

        self._logger.info("starting GenieACS API connection")
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._apiUrl = f"http://{self._host}:{self._port}"
        self._session = _requests.session()
        self._session.auth = (self._username, self._password)
        self._session.verify = False

    def __new__(cls: type[_Self], *args, **kwargs) -> _Self:
        if not cls._inst:
            cls._inst = super(GenieACS, cls).__new__(cls)
        return cls._inst

    def __del__(self):
        self._logger.info("closing GenieACS session")
        self._session.close()

    def _get_api_url(self, ep: GenieEndpoint):
        return f"http://{self._host}:{self._port}/{ep.value}"

    def get_devices(self) -> list[object]:
        resp = self._session.get(self._get_api_url(GenieEndpoint.DEVICES))
        if resp is None or resp.status_code != 200:
            return []
        try:
            data = resp.text
            data = data.replace("\n", "")
            data = data.replace("\r", "")
            data = _json.loads(data, object_hook=_device_object_hook)
        except:
            raise _JSONDecodeError
        self._logger.info(f"returning {len(data)} devices from GenieACS")
        return data
