#!/usr/bin/env python3

import json
from enum import Enum, unique
import requests
from requests.exceptions import JSONDecodeError


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

    def __del__(self):
        self.session.close()

    def get_api_url(self, ep: GenieEndpoint):
        return f"http://{self._host}:{self._port}/{ep.value}"

    def get_devices(self) -> list[dict]:
        resp = self.session.get(self.get_api_url(GenieEndpoint.DEVICES))
        if resp is None or resp.status_code != 200:
            return []
        try:
            data = resp.json(object_hook=_tr069_hook)
        except:
            raise JSONDecodeError
        return data


class TR069Value:
    _object = False
    _timestamp = None
    _type = None
    _value = None

    def __init__(self, d: dict):
        if "_object" in d:
            self._object = d["_object"]
        if "_timestamp" in d:
            self._timestamp = d["_timestamp"]
        if "_type" in d:
            self._type = d["_type"]
        if "_value" in d:
            self._value = d["_value"]


class TR069IGDBaicells:
    class TR069Baicells:
        class TR069Network:
            MapnQos: TR069Value
            _object: bool
            _writable: bool

        Network: TR069Network
        _writable: bool
        _object: bool

    Baicells: TR069Baicells

    class TR069DeviceInfo:
        AdditionalSoftwareVersion: TR069Value
        Description: TR069Value
        ModelName: TR069Value
        SerialNumber: TR069Value

    DeviceInfo: TR069DeviceInfo
    src: dict
    rest: dict


def _tr069_hook(d: dict):
    if "InternetGatewayDevice" in d:
        igd: dict = d["InternetGatewayDevice"]
        ret = TR069IGDBaicells()
        if "Baicells" in igd:
            bai = igd["Baicells"]
            ret.Baicells = ret.TR069Baicells()
            if "_writable" in bai:
                ret.Baicells._writable = bai["_writable"]
            if "_object" in bai:
                ret.Baicells._object = bai["_object"]
            if "Network" in bai:
                net = bai["Network"]
                ret.Baicells.Network = ret.Baicells.TR069Network()
                if "MapnQos" in net:
                    mapnqos = net["MapnQos"]
                    ret.Baicells.Network.MapnQos = TR069Value(mapnqos)
                    ret.Baicells.Network._object = net["_object"]
            del igd["Baicells"]
        if "DeviceInfo" in igd:
            di = igd["DeviceInfo"]
            ret.DeviceInfo = ret.TR069DeviceInfo()
            if "AdditionalSoftwareVersion" in di:
                ret.DeviceInfo.AdditionalSoftwareVersion = TR069Value(
                    di["AdditionalSoftwareVersion"]
                )
            if "Description" in di:
                ret.DeviceInfo.Description = TR069Value(di["Description"])
            if "ModelName" in di:
                ret.DeviceInfo.ModelName = TR069Value(di["ModelName"])
            if "SerialNumber" in di:
                ret.DeviceInfo.SerialNumber = TR069Value(di["SerialNumber"])
            del igd["DeviceInfo"]
        return ret
    return d
