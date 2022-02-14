#!/usr/bin/env python3
from easysnmp import Session
from easysnmp import SNMPVariable
from typing import Union
from mac_address import MACAddress
import requests

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

    def update_sonar(self) -> None:
        if self.old_mac():
            data = {
                "expired": 1,
                "api_key": sonar_apikey,
                "ip_address": self.hostname,
                "mac_address": self.old_mac(),
            }
            with requests.get(url=sonar_url, params=data) as resp:
                print(resp.text)
                self.release_old_mac()
        data = {
            "expired": 0,
            "api_key": sonar_apikey,
            "ip_address": self.hostname,
            "mac_address": self.mac_address(),
        }
        with requests.get(url=sonar_url, params=data) as resp:
            print(resp.text)

    def fetch_has_snmp(self) -> None:
        try:
            self.ue_info
        except:
            ue_info = self.snmp_get(".1.3.6.1.2.1.1.1.0")
            if ue_info is None:
                self.ue_has_snmp = False
            else:
                self.ue_info = ue_info.value
                self.ue_has_snmp = True

    def fetch_hw_info(self) -> str:
        try:
            return self.ue_type
        except:
            if self.has_snmp:
                telrad_check = self.telrad_12000_update_mac_address()
                if telrad_check:
                    self.ue_type = "Telrad 12000"
                    return self.ue_type
                else:
                    telrad_check = self.telrad_12300_update_mac_address()
                    if telrad_check:
                        self.ue_type = "Telrad 12300"
                        return self.ue_type
            else:
                print(f"Device %s isn't SNMP capable" % self.hostname)
            self.ue_type = "Unknonwn"
            return self.ue_type

    def telrad_12300_update_mac_address(self) -> Union[MACAddress, None]:
        mac = self.snmp_get(".1.3.6.1.2.1.2.2.1.6.7")
        if mac is None:
            return None
        if isinstance(mac.value, str):
            mac = mac.value.encode("utf-8").hex().replace("c2", "").replace("c3", "")
            if not len(mac) >= 12:
                mac = self.snmp_get(".1.3.6.1.2.1.2.2.1.6.2")
                if mac is None:
                    return None
                if isinstance(mac.value, str):
                    mac = (
                        mac.value.encode("utf-8")
                        .hex()
                        .replace("c2", "")
                        .replace("c3", "")
                    )
                    if len(mac) >= 12:
                        try:
                            self.mac = MACAddress(mac)
                        except:
                            return None

                    else:
                        return None
                else:
                    return None
            try:
                if self.mac != mac:
                    self.mac_to_release = mac
                    self.need_to_release = True
            except:
                pass
            try:
                self.mac = MACAddress(mac)
            except:
                return None
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

    def release_old_mac(self) -> None:
        try:
            del self.mac_to_release
        finally:
            self.need_to_release = False

    def old_mac(self) -> Union[None, MACAddress]:
        try:
            return self.mac_to_release
        except:
            return None

    def __repr__(self):
        return self.hostname

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

    def __str__(self) -> str:
        return self.hostname
