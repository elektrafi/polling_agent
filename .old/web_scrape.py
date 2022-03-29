#!/usr/bin/env python3
from typing import Union
from baicells import Baicells
from pprint import pprint
import requests.cookies as cookies
import xml.etree.ElementTree as ET
import requests
from functools import reduce
from mac_address import MACAddress
import re

from urllib3 import disable_warnings

disable_warnings()


class WebScraper:
    def __init__(
        self,
        addr: str,
        username: str = "admin",
        password: str = "EFI_Buna2020",
    ) -> None:
        self.host = addr
        self.username = username
        self.password = password
        self.baseUrl = f"http://{self.host}"
        self.model = None
        self.session = requests.session()
        self.session.auth = (self.username, self.password)
        self.session.verify = False
        self.baicells = Baicells(addr, username, password)
        self.init()

    def init(self) -> None:
        try:
            timeout = 1
            resp = None
            while resp is None:
                try:
                    resp = self.session.get(
                        self.baseUrl,
                        verify=False,
                        timeout=timeout,
                        allow_redirects=True,
                    )
                except:
                    if timeout > 10:
                        raise requests.ConnectTimeout
                    pass
                finally:
                    timeout += 3
            if resp is None:
                return
            header = resp.headers
            if "WWW-Authenticate" in header:
                resp = None
                timeout = 1
                while resp is None:
                    try:
                        resp = self.session.get(
                            self.baseUrl,
                            verify=False,
                            timeout=timeout,
                            allow_redirects=True,
                        )
                    except:
                        if timeout > 10:
                            raise requests.ConnectTimeout
                    finally:
                        timeout += 3
                if resp is None:
                    return
                auth = header["WWW-Authenticate"]
                indoor = re.compile(
                    """<title>.+?11ac.+?[bB]roadband.+[rR]outer.*?</title>"""
                )
                outdoor = re.compile(
                    """<title>(.+?[oO]utdoor.+?[rR]outer.*?)|(.*?[Bb][Ee][cC].+?6900.*?)</title>"""
                )
                if re.search(outdoor, resp.text):
                    self.model = "BEC6900"
                elif re.search(indoor, resp.text):
                    self.model = "BEC6500"
                else:
                    print(
                        f"BEC FOUND NOT 6900:\n\tIP: {self.baseUrl}\n\tAuth header:{auth}"
                    )
            elif re.search(re.compile("[sS][tT][oO][kK]"), resp.text):
                self.model = "OD06"
            else:
                print(f"SOMETHING FOUND:\n\tIP{self.baseUrl}\n\tHeaders: {header}")
                resp.text
        except requests.exceptions.SSLError:
            print(f"SSL ERROR from {self.baseUrl}")
        except requests.ConnectTimeout:
            if re.match(re.compile("https://(\d{1,3}\.){3}\d{1,3}/?"), self.baseUrl):
                print(f"--Failed after HTTP and HTTPS: {self.baseUrl}")
                return
            else:
                print(f"HTTP did not work for {self.baseUrl}, trying HTTPS")
                self.baseUrl = f"https://{self.host}"
                self.session = requests.session()
                self.session.auth = (self.username, self.password)
                self.session.verify = False
                self.init()

    def getHomepage(self) -> requests.Response:
        try:
            return self.session.get(self.baseUrl, verify=False, timeout=5)
        except:
            raise LookupError("Could not fetch CPE's homepage")

    def getDeviceStatusPage(self) -> Union[requests.Response, None]:
        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.get(
                    f"{self.baseUrl}/cgi-bin/status_deviceinfo.asp",
                    verify=False,
                    timeout=timeout,
                    allow_redirects=True,
                )
            except:
                if timeout > 10:
                    raise requests.ConnectTimeout(
                        "Could not fetch CPE's device status page"
                    )
            finally:
                timeout += 3
        return resp

    def getMacAddress(self) -> Union[MACAddress, None]:
        try:
            mac = self.parseMacAddress()
            return (
                MACAddress(mac)
                if mac and self.model in ["BEC6500", "BEC6900", "OD06"]
                else None
            )
        except LookupError:
            print(f"Regex parse to find mac address failed {self.baseUrl}")
            return None
        except requests.ConnectTimeout:
            print(
                f"Couldn't connect to the status page of {self.baseUrl} even with multiple tries"
            )
            return None
        except PermissionError:
            print(f"Incorrect username/password for the status page of {self.baseUrl}")
            return None

    def parseMacAddress(self) -> Union[str, None]:
        try:
            if self.model in ["OD06"]:
                mac = self.baicells.get_mac_address()
                return mac
            page = self.getDeviceStatusPage()
            if page is None:
                return None
            if page.status_code == 401:
                raise PermissionError("Access control issue or incorrect credentials")
            match = re.search(
                re.compile(
                    """[Mm][aA][cC].*?[aA]ddress[\w\s<>:/]+?(([\da-fA-f0-9]{2}\:){5}[\da-fA-F0-9]{2})"""
                ),
                page.text,
            )
            if not match:
                raise LookupError(
                    "Could not find device MAC address on CPE's status page"
                )
            return reduce(lambda x, y: x if len(x) > len(y) else y, match.groups())
        except Exception as e:
            raise e
