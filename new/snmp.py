#!/usr/bin/env python3
from easysnmp import SNMPVariable, Session
from .model.mac_address import MACAddress
import logging


class SNMP(object):
    hostname: str
    snmp: Session
    has_snmp: bool = True
    logger = logging.getLogger(__name__)

    def __init__(self, hostname: str):
        self.hostname = hostname
        self.snmp = Session(
            hostname=self.hostname,
            version=2,
            community="public",
            timeout=3,
            retries=2,
        )

    def try_check_telrad_12000(self) -> bool:
        try:
            check = self._snmp_get(".1.3.6.1.4.1.17713.20.2.1.4.2.0")
            if check is None:
                return False
            check = check.value
            if check is None:
                return False
            return "12000" in check
        except:
            return False

    def get_bec_mac_address(self) -> MACAddress | None:
        try:
            check = self.snmp.walk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "eth0"), None
            )
            mac = self._snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            self.has_snmp = False
            self.logger.error(
                f"SNMP for BEC {self.hostname} failed while matching eth0"
            )
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex()
        if len(mac) > 12:
            mac = mac.replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            return mac
        else:
            self.logger.error(
                f"SNMP for BEC {self.hostname} failed (maybe because of c2/c3 removal)"
            )
        return None

    def get_telrad_12300_mac_address(self) -> MACAddress | None:
        try:
            check = self.snmp.walk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "eth0"), None
            )
            mac = self._snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            self.has_snmp = False
            self.logger.error(
                f"SNMP for Telrad 12300 {self.hostname} failed while matching eth0"
            )
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex()
        if len(mac) > 12:
            mac = mac.replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            return mac
        return None

    def get_telrad_12000_mac_address(self) -> MACAddress | None:
        mac = self._snmp_get(".1.3.6.1.4.1.17713.20.2.1.3.13.0")
        if mac is None:
            return None
        if isinstance(mac.value, str) and len(mac.value) > 12:
            mac = MACAddress(mac.value)
            return mac
        else:
            return None

    def get_wac104_mac_address(self) -> MACAddress | None:
        try:
            check = self.snmp.walk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "lan4"), None
            )
            mac = self._snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            self.logger.error(
                f"SNMP for WAC104 {self.hostname} failed while matching lan4"
            )
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex()
        if len(mac) > 12:
            mac = mac.replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            return mac
        else:
            self.logger.error(
                f"SNMP for WAC104 {self.hostname} failed (maybe because of c2/c3 removal)"
            )
        return None

    def get_device_info(self) -> str | None:
        if not self.has_snmp:
            return None
        try:
            ue_info = self._snmp_get(".1.3.6.1.2.1.1.1.0")
        except:
            self.has_snmp = False
            return None
        if not ue_info or not ue_info.value or not isinstance(ue_info.value, str):
            self.has_snmp = False
            return None
        return ue_info.value

    def _snmp_get(self, oid: str) -> None | SNMPVariable:
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
