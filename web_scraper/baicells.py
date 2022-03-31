#!/usr/bin/env python3

from typing import (
    Callable as _Callable,
    Coroutine as _Coroutine,
    AsyncIterable as _AsyncIterable,
    Iterable as _Iterable,
)
import xml.etree.ElementTree as _ET
import re as _re
import functools as _functools
from urllib3 import disable_warnings as _disable_warnings
import logging as _logging
from aiohttp import (
    ClientSession as _ClientSession,
    BasicAuth as _BasicAuth,
    ClientSSLError,
    ClientConnectionError,
)
from asyncio import (
    get_event_loop as _get_loop,
    gather as _gather,
    sleep as _sleep,
)
from model.atoms import Item as _Item
from model.network import IMEI as _IMEI, IMSI as _IMSI, MACAddress as _MACAddress


_disable_warnings()


class Baicells:
    _logger = _logging.getLogger(__name__)
    _username: str = "admin"
    _password: str = "EFI_Buna2020"
    _auth: _BasicAuth = _BasicAuth(
        encoding="utf-8", login=_username, password=_password
    )

    @classmethod
    async def execute(cls, session: _ClientSession, func):
        cls._logger.debug(f"name: {func.__name__}")
        ret = func(session=session)
        if isinstance(ret, _AsyncIterable):
            items = list()
            async for item in ret:
                items.append(item)
            return items
        else:
            ret = await ret
        return ret

    @classmethod
    async def get_item(cls, item: _Item) -> _Item:
        host = str(item.ipv4)[: str(item.ipv4).index("/")]
        baseUrl = _re.sub(_re.compile(r"^(?!https)((http://)?)"), "https://", host)
        session = _ClientSession(
            base_url=baseUrl,
            auto_decompress=True,
            trust_env=True,
            auth=cls._auth,
            loop=_get_loop(),
        )
        await cls.login(session)
        value: dict[str, _Callable] = {}
        value["imei"] = cls.get_imei
        value["mac_address"] = cls.get_mac_address
        value["serial_number"] = cls.get_serial_number
        value["imsi"] = cls.get_imsi
        value["tx_power"] = cls.get_tx_power
        value["data_rates"] = cls.get_rates
        value["bandwidth"] = cls.get_bandwidth
        value["enbid"] = cls.get_enb_id
        value["cell_id"] = cls.get_cell_id
        value["earfcn"] = cls.get_earfcn
        value["pci"] = cls.get_pci
        value["sinr"] = cls.get_sinr
        value["rsrp"] = cls.get_rsrp
        value["rsrq"] = cls.get_rsrq
        value["rssi"] = cls.get_rssi

        wait: dict[str, _Coroutine[None, None, list[str]]] = {}
        for k in value:
            wait[k] = cls.execute(session, value[k])
        ret = cls._assign({k: await v for (k, v) in wait.items()})

        await session.close()
        return ret

    @staticmethod
    def _assign(d: dict[str, list[str]]) -> _Item:
        i: _Item = _Item()
        i.imei = _IMEI(d["imei"][0]) if "imei" in d else None
        i.imsi = _IMSI(d["imsi"][0]) if "imsi" in d else None
        i.mac_address = _MACAddress(d["mac_address"][0]) if "mac_address" in d else None
        i.serial_number = d["serial_number"][0] if "serial_number" in d else None
        i.tx_power = d["tx_power"][0] if "tx_power" in d else None
        i.rx_rate = d["data_rates"][0] if "data_rates" in d else None
        i.tx_rate = (
            d["data_rates"][1]
            if "data_rates" in d and len(d["data_rates"]) > 1
            else None
        )
        i.bandwidth = d["bandwidth"][0] if "bandwidth" in d else None
        i.enb_id = d["enbid"][0] if "enbid" in d else None
        i.cell_id = d["cell_id"][0] if "cell_id" in d else None
        i.earfcn = d["earfcn"][0] if "earfcn" in d else None
        i.pci = d["pci"][0] if "pci" in d else None
        i.sinr = d["sinr"][0] if "sinr" in d else None
        i.rsrp = (
            str(
                sum(float(x) for x in d["rsrp"])
                // sum(1 for x in d["rsrp"] if float(x))
            )
            if "rsrp" in d
            else None
        )
        i.rsrq = (
            str(
                sum(float(x) for x in d["rsrq"])
                // sum(1 for x in d["rsrq"] if float(x))
            )
            if "rsrq" in d
            else None
        )
        i.rssi = (
            str(
                sum(float(x) for x in d["rssi"])
                // sum(1 for x in d["rssi"] if float(x))
            )
            if "rssi" in d
            else None
        )
        return i

    @staticmethod
    def check_login(func):
        @_functools.wraps(func)
        async def check(cls, session, *args, **kwargs):
            if await cls.need_to_login(session):
                await cls.login(session)
            return await func(cls, session, *args, **kwargs)

        return check

    @staticmethod
    def print_name(func):
        @_functools.wraps(func)
        async def print_wrap(cls, *args, **kwargs):
            print(f"Running function {func.__name__}")
            ret = await func(cls, *args, **kwargs)
            print(f"Finished running function {func.__name__}")
            return ret

        return print_wrap

    @classmethod
    async def init_stok(cls, session: _ClientSession) -> str:
        try:
            async with session.get(
                url="/cgi-bin/login.cgi",
                params={"Command": "getLoginStok"},
                headers={"DNT": "1", "Referer": f"{session._base_url}/Login.html"},
                ssl=False,
            ) as resp:
                text = await resp.text("utf-8")
                cls._logger.debug(f"init_stok.text: {text}")
                cls._logger.debug(f"init_stok.cookies: {resp.cookies.items()}")
                cls._logger.debug(f"init_stok.headers: {resp.headers.items()}")
                cls._logger.debug(f"init_stok.resp.yield: :{resp}")
                return await resp.text(encoding="utf-8")
        except ClientSSLError:
            return ""
        except:
            cls._logger.exception("baicells http error", stack_info=True)
        return ""

    @classmethod
    async def get_stok_from_page_head(cls, session: _ClientSession, resp: str) -> str:
        data = resp
        cls._logger.debug(f"get_stok_from_page_head.data: :{data}")
        if data is None:
            cls._logger.error("No text in request to get stok")
            raise ValueError
        stokRe = _re.compile(
            r"""<\s*?meta\s+?name[\s="]+?stok[\s"]+?content[="\s]+?([0-9a-zA-Z]+)"[\s]*?>"""
        )
        search = _re.search(stokRe, data)
        cls._logger.debug(f"get_stok_from_page_head.search: :{search}")
        if search:
            for match in search.groups():
                cls._logger.debug(f"get_stok_from_page_head.match: :{match}")
                return match
        return ""

    @classmethod
    async def get_stok(
        cls, session: _ClientSession, respStok: str, name: str = "login"
    ) -> str:
        data = respStok
        cls._logger.debug(f"get_stok.data: :{data}")
        stokTree = _ET.fromstring(data)
        cls._logger.debug(f"get_stok.stokTree: :{stokTree}")
        stok = stokTree.find(f"{name}_stok")
        cls._logger.debug(f"get_stok.stok: :{stok}")

        if stok is None:
            cls._logger.error(
                "Nonce info (stok) not found in login init XML for Baicells device"
            )
            raise ValueError

        if stok.text is None:
            return ""
        return stok.text

    @classmethod
    async def login(cls, session: _ClientSession) -> None:
        init = await cls.init_stok(session)
        stok = await cls.get_stok(session, init)
        cls._logger.debug(f"login.stok: {stok}")
        try:
            async with session.post(
                allow_redirects=True,
                url=f"/cgi-bin/login.cgi",
                data={
                    "Command": "setLOGINvalue",
                    "input_URN": cls._username,
                    "rand_PWD": cls._password,
                },
                headers={
                    "DNT": "1",
                    "Referer": f"{session._base_url}/Login.html",
                    "Connection": "keep-alive",
                    "X-Stok": stok,
                },
                ssl=False,
            ) as resp:
                text = await resp.text("utf-8")
                cls._logger.debug(f"login.text: {text}")
                cls._logger.debug(f"login.cookies: {resp.cookies.items()}")
                cls._logger.debug(f"login.headers: {resp.headers.items()}")
                ses = resp.headers.get("Set-Cookie")
                if ses:
                    c = {
                        ses.split("=")[0]: ses.split("=")[1][
                            : ses.split("=")[1].index(";")
                        ]
                    }
                    session.cookie_jar.update_cookies(c)
        except ClientSSLError:
            pass
        except:
            cls._logger.exception(
                "Could not connect to login page to loogin to Baicells device",
                stack_info=True,
            )

    @classmethod
    async def get_login_state(cls, session: _ClientSession) -> _ET.Element:
        try:
            async with session.get(
                url="/cgi-bin/common.cgi",
                params={"Command": "GetLoginState"},
                headers={
                    "DNT": "1",
                    "Referer": f"{session._base_url}/overview.html",
                    "Connection": "keep-alive",
                },
                ssl=False,
            ) as resp:
                text = await resp.text(encoding="utf-8")
                infoTree = _ET.fromstring(text)
                cls._logger.debug(f"get_login_state.infoTree: {infoTree}")
                if infoTree is None:
                    cls._logger.error(
                        "Unable to parse Baicells login state page into XML"
                    )
                    raise _ET.ParseError

            ret = infoTree.find("WebServer")

            if ret is None:
                cls._logger.error(
                    f"Unable to find the WebServer tag on common.cgi: {infoTree.items()}"
                )
                raise ValueError
            cls._logger.debug(f"get_login_state.ret: :{ret}")
            return ret
        except ClientSSLError:
            pass
        except:
            cls._logger.error("Could not connect to Baicells overview page")
            raise ClientConnectionError
        return _ET.Element("")

    @classmethod
    async def need_to_login(cls, session: _ClientSession) -> bool:
        state = await cls.get_login_state(session)
        if state is None:
            return True
        redirect = state.find("Redirect")
        if redirect is None or not redirect.text:
            return True
        return int(redirect.text) == 1

    @classmethod
    async def get_cgi(
        cls, session: _ClientSession, page: str, command: str, xml: str
    ) -> _ET.Element:
        try:
            async with session.get(
                allow_redirects=True,
                url=page,
                params={"Command": command},
                headers={
                    "DNT": "1",
                    "Referer": f"{session._base_url}/overview.html",
                    "Connection": "keep-alive",
                },
                ssl=False,
            ) as sysInfo:
                text = await sysInfo.text(encoding="utf-8")
                parser = _ET.XMLParser()
                parser.feed(text)
                build: _ET.TreeBuilder = parser.target
                root = build.close()

                if root is None:
                    cls._logger.error("Unable to parse Baicells sysinfo page into XML")
                    raise _ET.ParseError

                ret = root.find(xml)
                return ret if ret else _ET.Element("")

        except ClientSSLError as e:
            cls._logger.exception(f"baicells SSL error", stack_info=True)
            raise e
        except:
            cls._logger.exception(
                "Could not connect to Baicells sysinfo page", stack_info=True
            )
            raise ClientConnectionError

    @classmethod
    async def get_cgi_value(
        cls,
        session: _ClientSession,
        xml_tags: _Iterable[str],
        fetch_fn: _Callable[[_ClientSession], _Coroutine[None, None, _ET.Element]],
    ) -> _AsyncIterable[str]:
        info = await fetch_fn(session)
        cls._logger.debug(f"xml group: {info}")
        for xml_tag in xml_tags:
            info = info.find(xml_tag)
            cls._logger.debug(f"xml tag: {info}")
            cls._logger.debug(
                f"xml tags text: {info.text if info is not None else 'N/A'}"
            )
            if info is None:
                cls._logger.error("xml group not found")
                return
            text = info.text
            if text is None:
                cls._logger.error("no text on xml tag")
                return
            yield text

    @classmethod
    async def get_page(cls, session: _ClientSession, url: str) -> str:
        try:
            async with session.get(
                url=url,
                ssl=False,
            ) as resp:
                return await resp.text(encoding="utf-8")
        except ClientSSLError:
            pass
        except:
            cls._logger.error("Could not connect to Baicells sysinfo page")
            raise ClientConnectionError
        return ""

    @classmethod
    async def update_settings(
        cls,
        session: _ClientSession,
        url: str,
        data: dict[str, str],
    ) -> None:
        try:
            s = await cls.get_upnp_page(session)
            stok = await cls.get_stok_from_page_head(session, s)
            async with session.post(
                url=url,
                data=data,
                headers={
                    "DNT": "1",
                    "Referer": f"{session._base_url}/overview.html",
                    "Connection": "keep-alive",
                    "X-Stok": stok,
                },
                ssl=False,
            ):
                pass
        except ClientSSLError:
            pass
        except:
            cls._logger.error("Could not connect to Baicells upnp update page")
            raise ClientConnectionError

    @classmethod
    async def get_firewall_page(cls, session: _ClientSession) -> str:
        return await cls.get_page(session, "/system_security.html")

    @classmethod
    async def get_tr069_page(cls, session: _ClientSession) -> str:
        return await cls.get_page(session, "/tr069.html")

    @classmethod
    async def get_upnp_page(cls, session: _ClientSession) -> str:
        return await cls.get_page(session, "/upnp.html")

    @classmethod
    async def update_firewall_settings(cls, session: _ClientSession) -> None:
        data = {
            "Command": "systemSecuritySet",
            "customSettings": "1",
            "WebLoginEnabled": "1",
            "RemoteTelnetEnabled": "1",
            "RemoteSshEnabled": "1",
            "AclEnabled": "0",
            "sysfwBlockPortScanHead": "0",
            "sysfwBlockSynFloodHead": "0",
            "sysfwSPIFWHead": "0",
        }
        return await cls.update_settings(
            session, "/cgi-bin/sec_ddos_filtering.cgi", data
        )

    @classmethod
    async def update_tr069_settings(cls, session: _ClientSession) -> None:
        data = {
            "Command": "setTR069value",
            "TR_ENABLE": "1",
            "TR_ACS_URL": "http://10.244.1.21:7547",
            "TR_ACS_USER": "EFITR69",
            "TR_ACS_PASS": "",
            "TR_INFORM_ENABLE": "1",
            "TR_INFORM_INTERVAL": "360",
            "TR_CR_USER": "cpe",
            "TR_CR_PASS": "EFI_Buna2020!1",
        }
        return await cls.update_settings(session, "/cgi-bin/tr069.cgi", data)

    @classmethod
    async def update_upnp_settings(cls, session: _ClientSession) -> None:
        return await cls.update_settings(
            session,
            "/cgi-bin/systemnetwork.cgi",
            {"Command": "UPNPSetting", "upnpEnable": "1"},
        )

    @classmethod
    async def get_sysinfo(cls, session: _ClientSession) -> _ET.Element:
        return await cls.get_cgi(
            session, "/cgi-bin/systeminfo.cgi", "GetSetting", "sysinfo"
        )

    @classmethod
    async def get_wireless(cls, session: _ClientSession) -> _ET.Element:
        return await cls.get_cgi(
            session, "/cgi-bin/wirelessstatus.cgi", "GetWireless", "wireless"
        )

    @classmethod
    async def get_throughput(cls, session: _ClientSession) -> _ET.Element:
        return await cls.get_cgi(
            session, "/cgi-bin/throughput.cgi", "getThroughput", "netratelist"
        )

    @classmethod
    async def get_mac_address(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["idu_mac"], cls.get_sysinfo):
            yield x

    @classmethod
    async def get_imei(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["imestr"], cls.get_sysinfo):
            yield x

    @classmethod
    async def get_serial_number(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["mb_sn"], cls.get_sysinfo):
            yield x

    @classmethod
    async def get_rates(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(
            session, ["dl_rate", "ul_rate"], cls.get_throughput
        ):
            yield x

    @classmethod
    async def get_bandwidth(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interBandwidth"], cls.get_wireless):
            yield x

    @classmethod
    async def get_enb_id(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["intereNBid"], cls.get_wireless):
            yield x

    @classmethod
    async def get_cell_id(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interCellid"], cls.get_wireless):
            yield x

    @classmethod
    async def get_pci(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interpci"], cls.get_wireless):
            yield x

    @classmethod
    async def get_rssi(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interrssi"], cls.get_wireless):
            for item in _re.split(r"\s*/\s*", x):
                yield item

    @classmethod
    async def get_rsrp(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interrsrp"], cls.get_wireless):
            for item in _re.split(r"\s*/\s*", x):
                yield item

    @classmethod
    async def get_rsrq(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interrsrq"], cls.get_wireless):
            for item in _re.split(r"\s*/\s*", x):
                yield item

    @classmethod
    async def get_sinr(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["intersinr"], cls.get_wireless):
            yield x

    @classmethod
    async def get_tx_power(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["intertxpwr"], cls.get_wireless):
            yield x

    @classmethod
    async def get_imsi(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interIMSI"], cls.get_wireless):
            yield x

    @classmethod
    async def get_earfcn(cls, session: _ClientSession) -> _AsyncIterable[str]:
        async for x in cls.get_cgi_value(session, ["interEARFCN"], cls.get_wireless):
            yield x
