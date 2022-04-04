#!/usr/bin/env python3
import re as _re
import requests as _requests
from model.atoms import Account as _Account, Item as _Item, Name as _Name
from model.network import IMEI as _IMEI, IMSI as _IMSI, IPv4Address as _IPv4Address
import logging as _logging
from typing import Any as _Any, Iterable as _Iterable, AsyncIterable as _AsyncIterable
from enum import Enum as _Enum, unique as _unique
from typing_extensions import Self as _Self
from aiohttp.client import (
    ClientSession as _ClientSession,
    ClientResponse as _ClientResponse,
)
from aiohttp import BasicAuth as _BasicAuth
from concurrent.futures import ProcessPoolExecutor as _PPE

_exec = _PPE()


@_unique
class RaemisEndpoint(_Enum):
    SUBSCRIBERS = "/api/subscriber"
    SESSION = "/api/session"
    DATA_SESSIONS = "/api/data_session"


@_unique
class HTTPMethod(_Enum):
    GET = "GET"
    DELETE = "DELETE"
    POST = "POST"


class Raemis:
    _logger = _logging.getLogger(__name__)
    session: _ClientSession
    _username = "pollingAgent"
    _password = "EFI_Buna2020!1"
    _auth: _BasicAuth = _BasicAuth(login=_username, password=_password)
    apiUrl: str = "http://10.44.1.13"
    _inst: _Self | None = None

    @classmethod
    async def get_subscribers(cls) -> _Iterable[_Item]:
        data = list()
        try:
            cls._logger.info("creating items from raemis subscribers")
            async for data in cls._get_data(RaemisEndpoint.SUBSCRIBERS):
                data = await data.json()
                cls._logger.info(
                    f'returning {len(data) if data is not None else "N/A"} subscribers'
                )
                data = await cls._convert_api_subscribers(data)
        except:
            cls._logger.exception("raemis error", stack_info=True)
        return data

    @classmethod
    async def get_subscribers_json(cls) -> _Iterable[dict[str, _Any]]:
        data = None
        try:
            cls._logger.info("getting json from raemis for subscribers")
            async for data in cls._get_data(RaemisEndpoint.SUBSCRIBERS):
                data = await data.json()
                cls._logger.info(
                    f'returning {len(data) if data is not None else "N/A"} subscribers'
                )
        except:
            cls._logger.exception("raemis error", stack_info=True)
        return data

    @classmethod
    async def _convert_api_subscribers(
        cls, json: list[dict[str, str]]
    ) -> _Iterable[_Item]:
        return list(_exec.map(cls._convert_api_subscriber, json, chunksize=100))

    @classmethod
    def _convert_api_subscriber(cls, json: dict[str, str]) -> _Item:
        if "imei" in json and "imsi" in json and json["imei"] and json["imsi"]:
            equip = _Item()
            if "imei" in json and json["imei"]:
                equip.imei = _IMEI(json["imei"])
            if "imsi" in json and json["imsi"]:
                equip.imsi = _IMSI(json["imsi"])
            if "cell_id" in json and json["cell_id"]:
                equip.cell_id = json["cell_id"]
            if "msisdn" in json and json["msisdn"]:
                equip.sim_index = json["msisdn"]
            if "id" in json and json["id"]:
                equip._raemis_id = json["id"]
            if "local_ps_attachment" in json and json["local_ps_attachment"]:
                equip.attached = (
                    json["local_ps_attachment"].lower().strip() == "attached"
                )
        else:
            equip = _Item()
        if "name" in json and json["name"] and not json["name"].startswith("!"):
            name = cls._attempt_name_transform(json["name"])
            account = _Account(_Name(name)) if name else None
        else:
            account = None
        if equip and account:
            equip.account = account
            cls._logger.info(f"adding item from raemis: {equip}")

        return equip

    @classmethod
    def _attempt_name_transform(cls, n: str) -> str | None:
        if n.startswith("!") or n.startswith("_"):
            return None
        sp = r"\s+"
        amp = _re.compile(r"""([^_]+)\s+(&|and)\s+([^_]+)""")
        amps = r"""\1 & \3"""
        tow = _re.compile(r"""[sS][eE][tT][xX]\s*\d{1,4}""")
        index = _re.compile(r"""\d{5,6}""")
        mi = _re.compile(r"""([mM][iI](([lL][eE])|\.)?)?\s*[0-9.]+""")
        un = r"""\s*_+\s*"""
        naspl = r"""([-a-zA-Z'"0-9 &#@*\/.:;()]+)\s*,\s*([-a-zA-Z'"0-9 &#@*\/.:;()]+)"""
        nasub = r"""\2 \1"""
        tname = r"""(([Tt][eE][lL]([rR][aA][dD])?)?\s*([lL][Tt][eE])?\s*([cC][Pp][eE])?)?\s*"""
        tnum = r"""(12[30]00?)"""
        baname = r"""(([Bb][aA][iI]([cC][eE][lL][sS]?)?)|([oO][dD]?))?\s*"""
        banum = r"""0?6"""
        bename = r"""(([bB][eE][cC])|([rR][wW])|(([rR][iI][dD][gG][eE])?([wW][aA][vV][eE])?))?\s*"""
        becnum = r"""(7000|6[95]00)"""
        model = _re.compile(f"({tname}{tnum})|({baname}{banum})|({bename}{becnum})")

        name = _re.split(un, n)[0]
        name = _re.sub(sp, " ", name)
        name = _re.sub(naspl, nasub, name)
        name = _re.sub(sp, " ", name)
        name = _re.sub(amp, amps, name)
        name = _re.sub(sp, " ", name)
        return (
            name
            if not _re.fullmatch(mi, name)
            and not _re.fullmatch(index, name)
            and not _re.fullmatch(model, name)
            and not _re.fullmatch(tow, name)
            else None
        )

    @classmethod
    async def get_data_sessions(cls) -> _Iterable[_Item]:
        data = list()
        try:
            cls._logger.info("getting data sessions from raemis")
            async for data in cls._get_data(RaemisEndpoint.DATA_SESSIONS):
                data = await data.json()
                cls._logger.info(
                    f'returning {len(data) if data is not None else "N/A"} data session records'
                )
                data = await cls._convert_sessions_to_items(data)
        except:
            cls._logger.exception("raemis error", stack_info=True)
        return data

    @classmethod
    async def _convert_sessions_to_items(
        cls, d: list[dict[str, str]]
    ) -> _Iterable[_Item]:
        return list(_exec.map(cls._convert_session_to_item, d, chunksize=75))

    @classmethod
    def _convert_session_to_item(cls, i: dict[str, str]) -> _Item:
        ret = _Item()
        if "apn" in i and i["apn"]:
            ret.apn = i["apn"]
        if "imsi" in i and i["imsi"]:
            ret.imsi = _IMSI(i["imsi"])
        if "ip" in i and i["ip"]:
            ret.ipv4 = _IPv4Address(address=i["ip"], cidr_mask=22)
        cls._logger.debug(
            f'found ip address: {ret.ipv4 if ret.ipv4 else "N/A"} for item: {ret if ret else "UNKNOWN"}'
        )
        return ret

    @classmethod
    async def _del_data(
        cls, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> _AsyncIterable[_ClientResponse]:
        async for x in cls._request(HTTPMethod.DELETE, ep, data):
            try:
                yield x
            except:
                return

    @classmethod
    async def _post_data(
        cls, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> _AsyncIterable[_ClientResponse]:
        async for x in cls._request(HTTPMethod.POST, ep, data):
            try:
                yield x
            except:
                return

    @classmethod
    async def _get_data(cls, ep: RaemisEndpoint) -> _AsyncIterable[_ClientResponse]:
        async for x in cls._request(HTTPMethod.GET, ep):
            try:
                yield x
            except:
                return

    @classmethod
    async def _request(
        cls, method: HTTPMethod, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> _AsyncIterable[_ClientResponse]:
        try:
            async with _ClientSession(base_url=cls.apiUrl, auth=cls._auth) as session:
                resp = await session.request(
                    method=method.value, url=ep.value, data=data
                )
                try:
                    yield resp
                except:
                    resp.close()

        except:
            cls._logger.exception(
                f"unable to resolve HTTP {method.value} request to {ep.value}",
                stack_info=True,
            )
            raise _requests.ConnectionError
