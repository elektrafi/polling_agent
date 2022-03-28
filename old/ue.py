#!/usr/bin/env python3
from easysnmp import Session
from easysnmp import SNMPVariable
import easysnmp
from typing import Union
from mac_address import MACAddress
from requests import get as rget
from telnet_client import TelnetClient
from web_scrape import WebScraper

sonar_apikey = "f56e4e95-1790-4392-bf45-379ef2994d3c"
sonar_url = "https://elektrafi.sonar.software/api/dhcp"


class UE:
    def __init__(self, hostname: str) -> None:
        self.hostname = hostname
        self.snmp = easysnmp.Session(
            hostname=hostname, community="public", version=2, timeout=3, retries=2
        )
        self.ue_has_snmp = True
        self.need_to_release = False

    def find_imei(self):
        mac = self.mac_address()
        if mac is None:
            return
        mac = str(mac)
        if mac.startswith("80"):
            snmp_res = self.snmp_get(".1.3.6.1.4.1.17713.20.2.1.4.11.0")
            if snmp_res is None:
                return
            imei = snmp_res.value
            if imei is None:
                return
            self.imei = imei
        if mac.startswith("60"):
            snmp_res = self.snmp_get(".1.3.6.1.4.1.17453.4.1.8.0")
            if snmp_res is None:
                return
            imei = snmp_res.value
            if imei is None:
                return
            self.imei = imei

    def fetch_ue_info(self) -> None:
        try:
            ue_info = self.snmp_get(".1.3.6.1.2.1.1.1.0")
            if ue_info is None:
                self.ue_has_snmp = False
                self.scraper = WebScraper(self.hostname)
                mac = self.scraper.getMacAddress()
                self.ue_info = self.scraper.model
                if mac and isinstance(mac, MACAddress):
                    self.mac = mac
            else:
                self.ue_has_snmp = True
                if isinstance(ue_info.value, str):
                    self.ue_info = " ".join(ue_info.value.split()[0:3])
                else:
                    self.ue_info = "UNKNOWN"
                if isinstance(ue_info.value, str) and (
                    "bec" in ue_info.value.lower()
                    or "ridgewave" in ue_info.value.lower()
                ):
                    self.bec_snmp_update_mac_address()
                elif isinstance(ue_info.value, str) and "wap" in ue_info.value.lower():
                    self.wac104_snmp_update_mac_address()
                elif isinstance(ue_info.value, str) and "bai" in ue_info.value.lower():
                    pass
                else:
                    telrad_check = self.telrad_12000_update_mac_address()
                    if not telrad_check:
                        telrad_check = self.telrad_12300_update_mac_address()
        except:
            print(f"Died for {self.hostname}")
            return

    def wac104_snmp_update_mac_address(self) -> Union[MACAddress, None]:
        try:
            check = self.snmp.get_bulk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "lan4"), None
            )
            mac = self.snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            print(f"SNMP for WAC104 {self.hostname} failed while matching lan4")
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex().replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            try:
                if self.mac != mac:
                    self.mac_to_release = self.mac
                    self.need_to_release = True
            except:
                pass
            self.mac = mac
            return mac
        else:
            print(
                f"SNMP for WAC104 {self.hostname} failed (maybe because of c2/c3 removal)"
            )
        return None

    def bec_snmp_update_mac_address(self) -> Union[MACAddress, None]:
        try:
            check = self.snmp.get_bulk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "eth0"), None
            )
            mac = self.snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            print(f"SNMP for BEC {self.hostname} failed while matching eth0")
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex().replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            try:
                if self.mac != mac:
                    self.mac_to_release = self.mac
                    self.need_to_release = True
            except:
                pass
            self.mac = mac
            return mac
        else:
            print(
                f"SNMP for BEC {self.hostname} failed (maybe because of c2/c3 removal)"
            )
        return None

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
            except:
                pass
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
        Host: {self.get_host()} HW Address: {self.mac_address()} Info: {self.get_ue_info()}"""

    def __str__(self) -> str:
        sep = "==========================================="
        return f"""{sep}
        Host: {self.get_host()} HW Address: {self.mac_address()} Info: {self.get_ue_info()}"""
