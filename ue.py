#!/usr/bin/env python3
from binascii import Error
from easysnmp import Session
from easysnmp import EasySNMPError
from easysnmp import SNMPVariable
import easysnmp


class UE:
    async def __init__(self, hostname):
        self.hostname = hostname
        self.snmp = Session(
            hostname=hostname, community="public", version=2, timeout=2.5, retries=2
        )
        self.ue_has_snmp = True
        self.ue_type = None
        self.mac = None
        await self.find_type()

    async def get_info(self) -> SNMPVariable:
        try:
            self.ue_info = self.snmp.get(".1.3.6.1.2.1.1.1.0")
        except (EasySNMPError, Error):
            self.info = None
            self.ue_has_snmp = False
        return self.ue_info

    async def find_type(self):
        if self.ue_type:
            return self.ue_type
        try:
            telrad_check = await self.get_telrad_wan_mac()
            if telrad_check:
                self.mac = telrad_check.value
                self.ue_type = telrad_check
        except EasySNMPError:
            self.ue_has_snmp = False
        return self.ue_type

    async def get_telrad_wan_mac(self):
        if self.mac:
            return self.mac
        try:
            self.mac = self.snmp.get(".1.3.6.1.4.1.17713.20.2.1.3.2.0")
        except EasySNMPError:
            self.mac = None
        return self.mac

    def has_snmp(self):
        return self.ue_has_snmp

    def get_mac(self):
        return self.mac

    def __repr__(self):
        return self.hostname

    def snmp_get(self, oid: str) -> SNMPVariable:
        s = self.snmp.get(oid)
        return s[0] if type(s) is list else SNMPVariable(s)

    def __str__(self):
        return self.hostname
