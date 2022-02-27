#!/usr/bin/env python3
from typing import Union
import requests
from functools import reduce
from mac_address import MACAddress
import re


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
        self.init()

    def init(self) -> None:
        self.session = requests.session()
        self.session.auth = (self.username, self.password)
        try:
            resp = self.session.get(self.baseUrl, verify=False, timeout=2)
            header = resp.headers
            if "WWW-Authenticate" in header:
                resp = self.session.get(self.baseUrl, verify=False, timeout=5)
                auth = header["WWW-Authenticate"]
                if "6900" in auth:
                    self.model = "BEC6900"
                elif "BEC" in auth or "RidgeWave" in auth:
                    self.model = "BEC6500"
                else:
                    print(
                        f"BEC FOUND NOT 6900:\n\tIP: {self.baseUrl}\n\tAuth header:{auth}"
                    )
            elif "ETag" in header:
                self.model = "Baicells OD??"
            else:
                print(f"SOMETHING FOUND:\n\tIP{self.baseUrl}\n\tHeaders: {header}")
                resp.text
        except requests.exceptions.SSLError as ssl:
            print(f"SSL ERROR from {self.baseUrl}")
        except requests.exceptions.ConnectionError as ce:
            print(f'Connection error (usually "too many retries") from {self.baseUrl}')
            print("--Trying with https")
            self.baseurl = f"https://{self.host}"
            self.session = requests.session()
            self.session.auth = (self.username, self.password)
            try:
                resp = self.session.get(self.baseUrl, verify=False, timeout=2)
                print(
                    f"--Something with HTTPS\n\tIP: {self.baseUrl}\n\tHeaders: {resp.headers}"
                )
                resp = self.session.get(self.baseUrl, verify=False, timeout=5)
                print(resp.text)
            except:
                print(f"--FAILED AFTER HTTP AND HTTPS {self.baseUrl}")

    def getHomepage(self) -> str:
        try:
            return self.session.get(self.baseUrl).text
        except:
            raise LookupError("Could not fetch CPE's homepage")

    def getDeviceStatusPage(self) -> str:
        try:
            return self.session.get(f"{self.baseUrl}/cgi-bin/status_device.asp").text
        except:
            raise LookupError("Could not fetch CPE's device status page")

    def getMacAddress(self) -> Union[MACAddress, None]:
        try:
            return (
                MACAddress(self.parseMacAddress())
                if self.model == "BEC6900" or self.model == "BEC6500"
                else None
            )
        except LookupError:
            print(f"exception on parsing page for {self.baseUrl}")
            return None

    def parseMacAddress(self) -> str:
        try:
            page = self.session.get(f"{self.baseUrl}/cgi-bin/status_deviceinfo.asp")
            if page.status_code == 401:
                raise PermissionError("Access control issue or incorrect credentials")
            match = re.match(
                re.compile(
                    """[M][aA][cC].+[aA]ddress[\w\s<>\n\r\t/]+(([\da-fA-f]{2}\:){5}[\da-fA-F]{2})"""
                ),
                page.text,
            )
            if not match:
                print(page.text.replace(" ", ""))

                raise LookupError(
                    "Could not find device MAC address on CPE's status page"
                )
            return reduce(lambda x, y: x if len(x) > len(y) else y, match.groups())
        except Exception as e:
            raise e
