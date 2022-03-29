#!/usr/bin/env python3

from io import UnsupportedOperation
import xml.etree.ElementTree as ET
from typing import Callable
import requests
import re
import functools

from urllib3 import disable_warnings

disable_warnings()


class BECWebEmulator:
    def __init__(
        self, baseUrl: str, username: str = "admin", password: str = "EFI_Buna2020"
    ):
        self.username = username
        self.password = password
        baseUrl = re.sub(re.compile("^(?!http://)((https://)?)"), "http://", baseUrl)
        self.baseUrl = baseUrl
        self.session = requests.session()
        self.session.auth = (self.username, self.password)
        self.session.verify = False
        self.getPage()

    def getPage(self, name: str = "") -> requests.Response:
        url = f'{self.baseUrl[:-1] if self.baseUrl[-1] == "/" else self.baseUrl}/{name[1:] if name.startswith("/") else name }'
        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.get(url, timeout=timeout, verify=False)
            except:
                if timeout > 10:
                    raise ConnectionError(f"Could not connect to BEC device page {url}")
            finally:
                timeout += 3
        return resp

    def postPage(self, name: str, data: dict[str, str]) -> requests.Response:
        url = f'{self.baseUrl}{"" if self.baseUrl[-1] == "/" else "/"}/{name}'
        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.post(url, timeout=timeout, verify=False, data=data)
            except:
                if timeout > 10:
                    raise ConnectionError(f"Could not connect to BEC device page {url}")
            finally:
                timeout += 3
        return resp

    def checkFirewallPage(self, page: requests.Response, text: str = "Enabled") -> bool:
        patt = re.compile(
            f'firewallEnable[\\s\\w<>"/]+?checked[\\s\\w<>"/]+?{text}', re.IGNORECASE
        )
        return bool(re.search(patt, page.text))

    def isFirewallEnabled(self) -> bool:
        return self.checkFirewallPage(self.getPage("/cgi-bin/adv_firewall.asp"))

    def toggleFirewall(self, enabled: bool = False) -> bool:
        data = {
            "firewallEnable": "0" if not enabled else "1",
            "spiEnable": "0",
            "fwFlag": "1",
        }
        return self.checkFirewallPage(
            self.postPage("/cgi-bin/adv_firewall.asp", data),
            "Enabled" if enabled else "Disabled",
        )

    def disableFirewall(self) -> bool:
        return self.toggleFirewall()

    def enableFirewall(self) -> bool:
        return self.toggleFirewall(True)

    def updateSNMP(self, data: dict[str, str]) -> bool:
        resp = self.postPage("/cgi-bin/access_smp.asp", data)
        return self.checkSNMP(
            resp,
            True if data["SNMP_active"].lower() == "yes" else False,
            data["SNMP_get"],
        )

    def updateSNMPDefault(self) -> bool:
        data = {
            "SNMP_active": "Yes",
            "SNMP_get": "public",
            "SNMP_set": "private",
            "SNMP_trapManagerIP": "10.244.1.253",
            "SNMP_sysName": "BEC RidgeWave",
            "SNMP_sysContact": "ElektraFi, LLC",
            "SNMP_sysLocation": "SETX",
            "interface": "all",
            "SNMPv3_enable": "No",
            "Snmpflag": "1",
            "Snmpv3flag": "Yes",
            "SnmpFullflag": "Yes",
            "startTrapflag": "Yes",
            "trustIPflag": "N/A",
        }
        resp = self.postPage("/cgi-bin/access_snmp.asp", data)
        return self.checkSNMP(resp)

    def checkSNMP(
        self, page: requests.Response, enabled: bool = True, community: str = "public"
    ) -> bool:
        activePatt = re.compile(
            f'SNMP_active[\\s\\w=<>"/]+?checked[\\s\\w=<>"/]+?{"Activated" if enabled else "Deactivated"}',
            re.IGNORECASE,
        )
        communityPatt = re.compile(
            f'SNMP_get[\\s\\w=<>"/]+?value[\\s"=]+?{community}', re.IGNORECASE
        )
        return bool(re.search(activePatt, page.text)) and bool(
            re.search(communityPatt, page.text)
        )

    def updateCWMP(self, data: dict[str, str]) -> bool:
        resp = self.postPage("/cgi-bin/access_smp.asp", data)
        return self.checkCWMP(
            resp,
            True if data["CWMP_active"].lower() == "yes" else False,
            data["CWMP_get"],
        )

    def updateCWMPDefault(self) -> bool:
        data = {
            "CWMP_Active": "Yes",
            "CWMP_ACSURL": "http://10.0.44.21:7547",
            "CWMP_ACSUserName": "EFITR69",
            "CWMP_ACSPassword": "",
            "CWMP_ConnectionRequestPath": "/cpe",
            "CWMP_ConnectionRequestUserName": "cpe",
            "CWMP_ConnectionRequestPassword": "EFI_Buna2020!1",
            "CWMP_PeriodActive": "Yes",
            "CWMP_PeriodInterval": "360",
            "CWMPLockFlag": "0",
            "CwmpIndex": "99",
            "CWMP_nattServer": "",
            "CWMP_nattPeriod": "",
            "CWMP_stunActive": "No",
            "CWMP_stunServer": "",
            "CWMP_stunPort": "3478",
            "Cwmpflag": "1",
        }
        resp = self.postPage("/cgi-bin/access_cwmp.asp", data)

        return self.checkCWMP(resp)

    def checkCWMP(
        self, page: requests.Response, enabled: bool = True, community: str = "public"
    ) -> bool:
        activePatt = re.compile(
            f'CWMP_active[\\s\\w=<>"/]+?checked[\\s\\w=<>"/]+?{"Activated" if enabled else "Deactivated"}',
            re.IGNORECASE,
        )
        communityPatt = re.compile(
            f'CWMP_ACSPassword[\\s\\w=<>"/]+?value[\\s=]+?""', re.IGNORECASE
        )
        return bool(re.search(activePatt, page.text)) and bool(
            re.search(communityPatt, page.text)
        )
