#!/usr/bin/env python3
from enum import Enum, unique
import json
import requests
from requests.exceptions import JSONDecodeError
from ..genie_acs.device import device_object_hook
import logging


@unique
class GenieEndpoint(Enum):
    DEVICES = "devices"
    TASKS = "tasks"
    FAULTS = "faults"
    PRESETS = "presets"
    FILES = "files"
    PROVISIONS = "provisions"


class GenieACS:
    logger = logging.getLogger(__name__)
    _host: str
    _port: int
    _username: str
    _password: str
    apiUrl: str
    session: requests.Session

    def __init__(
        self,
        host: str = "10.244.1.21",
        port: int = 7557,
        username: str = "admin",
        password: str = "password",
    ):

        self.logger.info("starting GenieACS API connection")
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self.apiUrl = f"http://{self._host}:{self._port}"
        self.session = requests.session()
        self.session.auth = (self._username, self._password)
        self.session.verify = False

    def __del__(self):
        self.logger.info("closing GenieACS session")
        self.session.close()

    def get_api_url(self, ep: GenieEndpoint):
        return f"http://{self._host}:{self._port}/{ep.value}"

    def get_devices(self) -> list[object]:
        resp = self.session.get(self.get_api_url(GenieEndpoint.DEVICES))
        if resp is None or resp.status_code != 200:
            return []
        try:
            data = resp.text
            data = data.replace("\n", "")
            data = data.replace("\r", "")
            data = json.loads(data, object_hook=device_object_hook)
        except:
            raise JSONDecodeError
        self.logger.info(f"returning {len(data)} devices from GenieACS")
        return data
