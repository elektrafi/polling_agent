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


class TR069:
    class TR069InternetGatewayDevice:
        class TR069Baicells:
            class TR069Network:
                MapnQos: TR069Value

            Network: TR069Network

        Baicells: TR069Baicells

        class TR069DeviceInfo:
            AdditionalSoftwareVersion: TR069Value
            Description: TR069Value
            ModelName: TR069Value
            SerialNumber: TR069Value
            Manufacturer: TR069Value
            ProductClass: TR069Value

        DeviceInfo: TR069DeviceInfo

        LANDeviceNumberOfEntries: TR069Value
        WANDeviceNumberOfEntries: TR069Value

        class TR069ManagementServer:
            ConnectionRequestURL: TR069Value
            ConnectionRequestUsername: TR069Value
            ConnectionRequestPassword: TR069Value
            Password: TR069Value
            PeriodicInformEnable: TR069Value
            PeriodicInformInterval: TR069Value
            PeriodicInformTime: TR069Value
            URL: TR069Value
            Username: TR069Value

        ManagementServer: TR069ManagementServer

        class TR069WANDevice:
            class TR069WANConnectionDevice:
                class TR069WANIPConnection:
                    ConnectionStatus: TR069Value

    class TR069VirtualParameters:
        _object: bool
        SINR: TR069Value
        RSRQ: TR069Value
        RSRP: TR069Value
        LOCKED_PCI_LIST: TR069Value
        IS_PCI_LOCKED: TR069Value
        History: TR069Value

    class TR069DeviceId:
        _SerialNumber: str
        _ProductClass: str
        _OUI: str
        _Manufacturer: str

    InternetGatewayDevice: TR069InternetGatewayDevice
    VirtualParameters: TR069VirtualParameters
    _tags: list[str]
    _id: str
    _deviceId: TR069DeviceId


def _tr069_hook(d: dict):
    if "InternetGatewayDevice" in d:
        igd: dict = d["InternetGatewayDevice"]
        ret = TR069InternetGatewayDevice()
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

def _tr069_dyn_hook(d: dict):
