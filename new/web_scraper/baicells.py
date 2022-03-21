#!/usr/bin/env python3

from io import UnsupportedOperation
import xml.etree.ElementTree as ET
import requests
import re
import functools
from urllib3 import disable_warnings
import logging

disable_warnings()


class Baicells:
    logger = logging.getLogger(__name__)
    username: str
    password: str
    baseUrl: str
    loggedIn: bool
    stoks: dict

    def __init__(
        self, baseUrl: str, username: str = "admin", password: str = "EFI_Buna2020"
    ):
        self.username = username
        self.password = password
        baseUrl = re.sub(re.compile("^(?!https)((http://)?)"), "https://", baseUrl)
        self.baseUrl = baseUrl
        self.session = requests.session()
        self.session.auth = (self.username, self.password)
        self.session.verify = False
        self.loggedIn = False
        self.stoks = {}

    @staticmethod
    def check_login(func):
        @functools.wraps(func)
        def check(self, *args, **kwargs):
            if self.need_to_login():
                self.login()
            return func(self, *args, **kwargs)

        return check

    @staticmethod
    def print_name(func):
        @functools.wraps(func)
        def print_wrap(self, *args, **kwargs):
            print(f"Running function {func.__name__}")
            ret = func(self, *args, **kwargs)
            print(f"Finished running function {func.__name__}")
            return ret

        return print_wrap

    def init_stok(self) -> requests.Response:
        respStok = None
        timeout = 1
        while respStok is None:
            try:
                respStok = self.session.get(
                    self.baseUrl + "/cgi-bin/login.cgi",
                    params={"Command": "getLoginStok"},
                    verify=False,
                    allow_redirects=True,
                    headers={"DNT": "1", "Referer": f"{self.baseUrl}/Login.html"},
                    timeout=timeout,
                )
            except:
                if timeout > 7:
                    self.logger.error(
                        "Could not connect to login page of Baicells device"
                    )
                    raise requests.ConnectionError
            finally:
                timeout += 3

        if not respStok.status_code == 200 or respStok.text is None:
            self.logger.error(
                "Tried to load a page for a Baicells device that does not exitst here."
            )
            raise UnsupportedOperation

        return respStok

    def get_stok_from_page_head(self, resp: requests.Response) -> str:
        if resp.text is None:
            self.logger.error("No text in request to get stok")
            raise ValueError
        stokRe = re.compile(
            """<\s*?meta\s+?name[\s="]+?stok[\s"]+?content[="\s]+?([0-9a-zA-Z]+)"[\s]*?>"""
        )
        match = re.search(stokRe, resp.text)
        if match is None:
            self.logger.error("coulnd find stok in page head")
            raise ValueError
        return match.groups()[0]

    def get_stok(self, respStok: requests.Response, name: str = "login") -> str:
        stokTree = ET.fromstring(respStok.text)
        stok = stokTree.find(f"{name}_stok")

        if stok is None:
            self.logger.error(
                "Nonce info (stok) not found in login init XML for Baicells device"
            )
            raise ValueError

        if stok.text is None:
            return ""
        return stok.text

    def login(self) -> None:
        stok = self.get_stok(self.init_stok())

        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.post(
                    f"{self.baseUrl}/cgi-bin/login.cgi",
                    data={
                        "Command": "setLOGINvalue",
                        "input_URN": self.username,
                        "rand_PWD": self.password,
                    },
                    headers={
                        "DNT": "1",
                        "Referer": f"{self.baseUrl}/Login.html",
                        "Connection": "keep-alive",
                        "X-Stok": stok,
                    },
                    verify=False,
                    allow_redirects=True,
                )
            except:
                if timeout > 7:
                    self.logger.error(
                        "Could not connect to login page to loogin to Baicells device"
                    )
                    raise requests.ConnectionError
            finally:
                timeout += 3

    def get_login_state(self) -> ET.Element:
        timeout = 1
        sysInfo = None
        while sysInfo is None:
            try:
                sysInfo = self.session.get(
                    self.baseUrl + "/cgi-bin/common.cgi",
                    params={"Command": "GetLoginState"},
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "DNT": "1",
                        "Referer": f"{self.baseUrl}/overview.html",
                        "Connection": "keep-alive",
                    },
                )
            except:
                if timeout > 7:
                    self.logger.error("Could not connect to Baicells sysinfo page")
                    raise requests.ConnectionError
            finally:
                timeout += 3

        infoTree = ET.fromstring(sysInfo.text)

        if infoTree is None:
            self.logger.error("Unable to parse Baicells login state page into XML")
            raise ET.ParseError

        ret = infoTree.find("WebServer")

        if ret is None:
            self.logger.error("Unable to find sysinfo tag on Baicells login state page")
            raise ValueError
        return ret

    def need_to_login(self) -> bool:
        state = self.get_login_state()
        if state is None:
            return True
        redirect = state.find("Redirect")
        if redirect is None or not redirect.text:
            return True
        return int(redirect.text) == 1

    @check_login
    def get_sysinfo(self) -> ET.Element:
        timeout = 1
        sysInfo = None
        while sysInfo is None:
            try:
                sysInfo = self.session.get(
                    self.baseUrl + "/cgi-bin/systeminfo.cgi",
                    params={"Command": "GetSetting"},
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "DNT": "1",
                        "Referer": f"{self.baseUrl}/overview.html",
                        "Connection": "keep-alive",
                    },
                )
            except:
                if timeout > 7:
                    self.logger.error("Could not connect to Baicells sysinfo page")
                    raise requests.ConnectionError
            finally:
                timeout += 3

        infoTree = ET.fromstring(sysInfo.text)

        if infoTree is None:
            self.logger.error("Unable to parse Baicells sysinfo page into XML")
            raise ET.ParseError

        ret = infoTree.find("sysinfo")

        if ret is None:
            self.logger.error("Unable to find sysinfo tag on Baicells sysinfo page")
            raise ValueError
        return ret

    @check_login
    def get_page(self, url: str) -> requests.Response:
        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.get(
                    self.baseUrl + url,
                    verify=False,
                    allow_redirects=True,
                )
            except:
                if timeout > 7:
                    self.logger.error("Could not connect to Baicells sysinfo page")
                    raise requests.ConnectionError
            finally:
                timeout += 3
        return resp

    def get_firewall_page(self) -> requests.Response:
        return self.get_page("/system_security.html")

    def get_tr069_page(self) -> requests.Response:
        return self.get_page("/tr069.html")

    def get_upnp_page(self) -> requests.Response:
        return self.get_page("/upnp.html")

    @check_login
    def update_firewall_settings(self) -> None:
        stok = self.get_stok_from_page_head(self.get_firewall_page())
        resp = None
        timeout = 1
        while resp is None:
            try:
                resp = self.session.post(
                    self.baseUrl + "/cgi-bin/sec_ddos_filtering.cgi",
                    data={
                        "Command": "systemSecuritySet",
                        "customSettings": "1",
                        "WebLoginEnabled": "1",
                        "RemoteTelnetEnabled": "1",
                        "RemoteSshEnabled": "1",
                        "AclEnabled": "0",
                        "sysfwBlockPortScanHead": "0",
                        "sysfwBlockSynFloodHead": "0",
                        "sysfwSPIFWHead": "0",
                    },
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "DNT": "1",
                        "Referer": f"{self.baseUrl}/overview.html",
                        "Connection": "keep-alive",
                        "X-Stok": stok,
                    },
                )
            except:
                if timeout > 7:
                    self.logger.error(
                        "Could not connect to Baicells firewall update page"
                    )
                    raise requests.ConnectionError
            finally:
                timeout += 3
        if resp.text and not "<xml>" in resp.text:
            self.logger.error(
                "Did not get the correct response when updating firewall settings"
            )
            raise ValueError

    @check_login
    def update_tr069_settings(self) -> None:
        stok = self.get_stok_from_page_head(self.get_tr069_page())
        resp = None
        timeout = 1
        while resp is None:
            try:
                resp = self.session.post(
                    self.baseUrl + "/cgi-bin/tr069.cgi",
                    data={
                        "Command": "setTR069value",
                        "TR_ENABLE": "1",
                        "TR_ACS_URL": "http://10.0.44.21:7547",
                        "TR_ACS_USER": "EFITR69",
                        "TR_ACS_PASS": "",
                        "TR_INFORM_ENABLE": "1",
                        "TR_INFORM_INTERVAL": "360",
                        "TR_CR_USER": "cpe",
                        "TR_CR_PASS": "EFI_Buna2020!1",
                    },
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "DNT": "1",
                        "Referer": f"{self.baseUrl}/overview.html",
                        "Connection": "keep-alive",
                        "X-Stok": stok,
                    },
                )
            except:
                if timeout > 7:
                    self.logger.error(
                        "Could not connect to Baicells TR-069 update page"
                    )
                    raise requests.ConnectionError
            finally:
                timeout += 3
        if resp.text and not "<xml>" in resp.text:
            self.logger.error(
                "Did not get the correct response when updating TR-069 settings"
            )
            raise ValueError

    @check_login
    def update_upnp_settings(self) -> None:
        stok = self.get_stok_from_page_head(self.get_upnp_page())
        resp = None
        timeout = 1
        while resp is None:
            try:
                resp = self.session.post(
                    self.baseUrl + "/cgi-bin/systemnetwork.cgi",
                    data={"Command": "UPNPSetting", "upnpEnable": "1"},
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "DNT": "1",
                        "Referer": f"{self.baseUrl}/overview.html",
                        "Connection": "keep-alive",
                        "X-Stok": stok,
                    },
                )
            except:
                if timeout > 7:
                    self.logger.error("Could not connect to Baicells upnp update page")
                    raise requests.ConnectionError
            finally:
                timeout += 3
        if resp.text and not "<xml>" in resp.text:
            self.logger.error(
                "Did not get the correct response when updating upnp settings"
            )
            raise ValueError

    def get_mac_address(self) -> str:
        info = self.get_sysinfo()

        info = info.find("idu_mac")
        if info is None:
            self.logger.error("No MAC address information on Baicells sysinfo page")
            raise ValueError
        mac = info.text

        if mac is None:
            self.logger.error(
                "MAC address XML tag contains no information on sysinfo page of Baicells device"
            )
            raise ValueError

        return mac
