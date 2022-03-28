#!/usr/bin/env python3
import re as _re
import requests as _requests
from ..model.atoms import Account as _Account, Item as _Item, Name as _Name
from ..model.network import IMEI as _IMEI, IMSI as _IMSI
from ..pipeline import Pipeline as _Pipeline
import logging as _logging
from typing import Any as _Any
from enum import Enum as _Enum, unique as _unique
from typing_extensions import Self as _Self


@_unique
class RaemisEndpoint(_Enum):
    SUBSCRIBERS = "subscriber"
    SESSION = "session"
    DATA_SESSIONS = "data_session"


@_unique
class HTTPMethod(_Enum):
    GET = "GET"
    DELETE = "DELETE"
    POST = "POST"


class Raemis:
    # event_queue = multiprocessing.Queue()
    _logger = _logging.getLogger(__name__)
    session: _requests.Session
    _pipeline: _Pipeline = _Pipeline()
    apiUrl: str
    _inst: _Self | None = None

    def __init__(
        self,
        apiUrl: str = "http://10.44.1.13/api",
        username: str = "pollingAgent",
        password: str = "EFI_Buna2020!1",
    ) -> None:
        self._logger.info("starting Raemis API connection")
        self.session = _requests.session()
        self.session.verify = False
        self.session.auth = (username, password)
        self.apiUrl = apiUrl[:-1] if apiUrl[-1] == "/" else apiUrl
        self._auth = {"username": username, "password": password}
        self._post_data(RaemisEndpoint.SESSION, self._auth)

    def __new__(cls: type[_Self], *args, **kwargs) -> _Self:
        if not cls._inst:
            cls._inst = super(Raemis, cls).__new__(cls)
        return cls._inst

    # def event_receiver(self) -> None:
    #    self._start_event_receiver_server()
    #    self.logger.info("initialized raemis API connection")

    # def _start_event_receiver_server(self) -> None:
    #    try:
    #        self._eventReceiver = ThreadingHTTPServer(("0.0.0.0", 9999), EventReceiver)
    #        server_thread = threading.Thread(target=self._eventReceiver.serve_forever)
    #        server_thread.daemon = True
    #        server_thread.start()
    #        self.logger.info("event receiver server thread started")
    #    except:
    #        self.logger.exception("could not start event erceiver server")

    def __del__(self) -> None:
        try:
            # self._eventReceiver.shutdown()
            self._logger.info("Event receiver HTTP server shutdown")
        except:
            self._logger.error("event receiver HTTP server failed to shutdown")
        self.session.close()
        self._logger.info("HTTP API session to Raemis closed")

    def get_subscribers(self) -> list[tuple[_Item | None, _Account | None]]:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.SUBSCRIBERS).json()
        finally:
            self._logger.info(
                f'returning {len(data) if data is not None else "N/A"} subscribers'
            )
        return self._convert_api_subscribers(data)

    def get_subscribers_json(self) -> list[dict[str, _Any]]:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.SUBSCRIBERS).json()
        finally:
            self._logger.info(
                f'returning {len(data) if data is not None else "N/A"} subscribers'
            )
        return data

    def get_data_sessions(self) -> list[dict[str, _Any]] | None:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.DATA_SESSIONS).json()
        finally:
            self._logger.info(
                f'returning {len(data) if data is not None else "N/A"} data session records'
            )
        return data

    def _convert_api_subscribers(
        self, json: list[dict[str, str]]
    ) -> list[tuple[_Item | None, _Account | None]]:
        return list(self._pipeline.map(self._convert_api_subscriber, json))

    def _convert_api_subscriber(
        self, json: dict[str, str]
    ) -> tuple[_Item | None, _Account | None]:
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
            equip = None
        if "name" in json and json["name"] and not json["name"].startswith("!"):
            name = self._attempt_name_transform(json["name"])
            account = _Account(_Name(name)) if name else None
        else:
            account = None
        self._logger.info(f"adding raemis subscriber/item pair: {(equip, account)}")
        return (equip, account)

    def _attempt_name_transform(self, n: str) -> str | None:
        if n.startswith("!") or n.startswith("_"):
            return None
        sp = r"\s+"
        amp = _re.compile(r"""([^_]+)\s*(&|and)\s*([^_]+)""")
        amps = r"""\1 & \3"""
        tow = _re.compile(r"""[sS][eE][tT][xX]\s*\d{1,4}""")
        index = _re.compile(r"""\d{5,6}""")
        mi = _re.compile(r"""([mM][iI](([lL][eE])|\.)?)?\s*[0-9.]+""")
        un = r"""\s*_+\s*"""
        naspl = r"""([-a-zA-Z'"0-9 &#@*\/.:;()]+)\s*,\s*([-a-zA-Z'"0-9 &#@*\/.:;()]+)"""
        nasub = r"""\2 \1"""
        na = _re.compile(r"""([-a-zA-Z'"0-9#&@*\/.:;()]+\s*)+""")
        tname = r"""(([Tt][eE][lL]([rR][aA][dD])?)?\s*([lL][Tt][eE])?\s*([cC][Pp][eE])?)?\s*"""
        tnum = r"""(12[30]00?)"""
        baname = r"""(([Bb][aA][iI]([cC][eE][lL][sS]?)?)|([oO][dD]?))?\s*"""
        banum = r"""0?6"""
        bename = r"""(([bB][eE][cC])|([rR][wW])|(([rR][iI][dD][gG][eE])?([wW][aA][vV][eE])?))?\s*"""
        becnum = r"""(7000|6[95]00)"""
        model = _re.compile(f"({tname}{tnum})|({baname}{banum})|({bename}{becnum})")
        for part in _re.split(un, n):
            if (
                _re.match(index, part)
                or _re.match(tow, part)
                or _re.match(mi, part)
                or _re.match(model, part)
            ):
                continue
            name = _re.sub(sp, " ", part)
            name = _re.sub(naspl, nasub, name)
            name = _re.sub(sp, " ", name)
            name = _re.sub(amp, amps, name)
            name = _re.sub(sp, " ", name)
            if (
                _re.fullmatch(na, name)
                and "1200" not in name
                and "1230" not in name
                and "6500" not in name
                and "7000" not in name
                and "6900" not in name
                and "SETX" not in name
                and "setx" not in name
            ):
                return name
            elif (
                _re.match(na, name)
                and "1200" not in name
                and "1230" not in name
                and "6500" not in name
                and "7000" not in name
                and "6900" not in name
                and "SETX" not in name
                and "setx" not in name
            ):
                return name
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

    def _get_raemis_url(self, ep: RaemisEndpoint) -> str:
        return f"{self.apiUrl}/{ep.value}"

    def _del_data(
        self, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> _requests.Response:
        return self._request(HTTPMethod.DELETE, ep, data)

    def _post_data(
        self, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> _requests.Response:
        return self._request(HTTPMethod.POST, ep, data)

    def _get_data(self, ep: RaemisEndpoint) -> _requests.Response:
        return self._request(HTTPMethod.GET, ep)

    def _request(
        self, method: HTTPMethod, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> _requests.Response:
        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.request(
                    method.value,
                    self._get_raemis_url(ep),
                    timeout=timeout,
                    data=data if data else None,
                )
            except:
                if timeout > 60:
                    self._logger.error(
                        f"unable to resolve HTTP {method.value} request to {self._get_raemis_url(ep)}"
                    )
                    raise _requests.ConnectionError
            finally:
                timeout += 5
        self._logger.debug(
            f"HTTP request type {method.value} resolved with status code {resp.status_code}"
        )
        return resp
