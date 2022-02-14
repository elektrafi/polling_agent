#!/usr/bin/env python3
from easysnmp import Session
from easysnmp import SNMPVariable
from typing import Union
from mac_address import MACAddress
from requests import get as rget
from telnet_client import TelnetClient

sonar_apikey = "f56e4e95-1790-4392-bf45-379ef2994d3c"
sonar_url = "https://elektrafi.sonar.software/api/dhcp"


class UE:
    def __init__(self, hostname: str) -> None:
        self.hostname = hostname
        self.snmp = Session(
            hostname=hostname, community="public", version=2, timeout=3, retries=2
        )
        self.ue_has_snmp = True
        self.need_to_release = False
        self.telnet = TelnetClient(self.hostname)

    def update_sonar(self) -> None:
        if self.old_mac():
            data = {
                "expired": 1,
                "api_key": sonar_apikey,
                "ip_address": self.hostname,
                "mac_address": self.old_mac(),
            }
            with rget(url=sonar_url, params=data) as resp:
                self.release_old_mac()
        data = {
            "expired": 0,
            "api_key": sonar_apikey,
            "ip_address": self.hostname,
            "mac_address": self.mac_address(),
        }
        with rget(url=sonar_url, params=data) as resp:
            pass

    def fetch_has_snmp(self) -> None:
        try:
            self.ue_info
        except:
            ue_info = self.snmp_get(".1.3.6.1.2.1.1.1.0")
            if ue_info is None:
                self.ue_has_snmp = False
            else:
                self.ue_has_snmp = True
                if isinstance(ue_info.value, str):
                    self.ue_info = " ".join(ue_info.value.split()[0:2])

    def fetch_hw_info(self) -> None:
        if self.has_snmp:
            telrad_check = self.telrad_12000_update_mac_address()
            if not telrad_check:
                telrad_check = self.telrad_12300_update_mac_address()
        else:
            self.telnet_info = self.telnet.cmd("wan lte status")

    def telrad_12300_update_mac_address(self) -> Union[MACAddress, None]:
        mac = self.snmp_get(".1.3.6.1.2.1.2.2.1.6.7")
        if mac is None:
            return None
        mac = mac.value.encode("utf-8").hex().replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            try:
                if self.mac != mac:
                    self.mac_to_release = self.mac
                    self.need_to_release = True
            finally:
                self.mac = mac
            return self.mac
        return None

    def telrad_12000_update_mac_address(self) -> Union[MACAddress, None]:
        mac = self.snmp_get(".1.3.6.1.4.1.17713.20.2.1.3.2.0")
        if mac is None:
            return None
        if isinstance(mac.value, str) and len(mac.value) > 12:
            mac = MACAddress(mac.value)
            try:
                if self.mac != mac:
                    self.mac_to_release = mac
                    self.need_to_release = True
            except:
                pass
            self.mac = mac
            return self.mac
        else:
            return None

    def mac_address(self) -> Union[None, MACAddress]:
        try:
            return self.mac
        except:
            return None

    def has_snmp(self) -> bool:
        return self.ue_has_snmp

    def get_ue_info(self) -> Union[None, str]:
        try:
            return self.ue_info
        except:
            return None

    def release_old_mac(self) -> None:
        try:
            del self.mac_to_release
        finally:
            self.need_to_release = False

    def get_host(self) -> str:
        return self.hostname

    def old_mac(self) -> Union[None, MACAddress]:
        try:
            return self.mac_to_release
        except:
            return None

    def snmp_get(self, oid: str) -> Union[None, SNMPVariable]:
        try:
            s = self.snmp.get(oid)
            ret = (
                s[0]
                if isinstance(s, list)
                else (s if isinstance(s, SNMPVariable) else None)
            )
            if isinstance(ret, SNMPVariable) and ret.value == "NOSUCHOBJECT":
                return None
            else:
                return ret
        except:
            return None

    def __repr__(self) -> str:
        sep = "==========================================="
        return f"""{sep}
        Host: {self.get_host()}
        HW Address: {self.mac_address()}
        Info: {self.get_ue_info()}
        {'Telnet Info: ' + self.telnet_info if hasattr(self, 'telnet_info') else ''}
        sep"""

    def __str__(self) -> str:
        sep = "==========================================="
        return f"""{sep}
        Host: {self.get_host()}
        HW Address: {self.mac_address()}
        Info: {self.get_ue_info()}
        {'Telnet Info: ' + self.telnet_info if hasattr(self, 'telnet_info') else ''}
        sep"""
