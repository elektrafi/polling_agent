#!/usr/bin/env python3
from dataclasses import dataclass
import logging
from enum import Enum
from .ip_address import IPv4Address
from .mac_address import MACAddress
from ..snmp import SNMP


class UEManufacturer(Enum):
    BAICELLS = "Baicells"
    TELRAD = "Telrad"
    BEC = "BEC"
    NETGEAR = "Netgear"
    UNKNOWN = "Unknown"


class UEModel(Enum):
    OD06 = "OD06"
    BEC6900 = "RidgeWave 6900"
    BEC6500 = "RidgeWave 6500"
    BEC7000 = "RidgeWave 7000"
    T12000 = "12000 Series"
    T12300 = "12300 Series"
    WAC104 = "WAC104 with ElektraFi-RT Firmware"
    UNKNOWN = "Unknown Device Type"


@dataclass
class Address:
    sonar_id: int | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    zip_code: str | None = None

    def __str__(self) -> str:
        return f"""
        <<
            [Address] sonar id: {self.sonar_id}
            address: {self.line1} {self.line2}, {self.city}, {self.zip_code}
        >>"""

    def __repr__(self) -> str:
        return f"""
        <<
            [Address] sonar id: {self.sonar_id}
            address: {self.line1} {self.line2}, {self.city}, {self.zip_code}
        >>"""


@dataclass
class Client:
    sonar_id: int | None = None
    name: str | None = None
    address: Address | None = None

    def __init__(self, name=None):
        self.address = Address()
        self.name = name

    def __str__(self) -> str:
        return f"""
        ||
          [Client] name: {self.name}
          sonar id: {self.sonar_id}
          address: {str(self.address)}
        ||
        """

    def __repr__(self) -> str:
        return f"""
        ||
          [Client] name: {self.name}
          sonar id: {self.sonar_id}
          address: {str(self.address)}
        ||
        """


@dataclass
class UE(object):
    logger = logging.getLogger(__name__)
    client: Client
    mac_address: MACAddress | None = None
    ipv4: IPv4Address | None = None
    sonar_id: int | None = None
    linked_to_account: bool = False
    info: str | None = None
    imei: str | None = None
    imsi: str | None = None
    _raemis_id: str | None = None
    cell_id: str | None = None
    sim_index: str | None = None
    rsrp: str | None = None
    rsrq: str | None = None
    rssi: str | None = None
    eci: str | None = None
    earfcn: str | None = None
    sinr: str | None = None
    bandwidth: str | None = None
    tx_rate: str | None = None
    tx_power: str | None = None
    rx_rate: str | None = None
    rx_power: str | None = None
    rx_mcs: str | None = None
    tx_mcs: str | None = None
    mcc: str | None = None
    mnc: str | None = None
    apn: str | None = None
    signal_quality: str | None = None

    attached: bool = False
    _tag: str | None = None
    _snmp: SNMP | None = None
    model: UEModel = UEModel.UNKNOWN
    manufacturer: UEManufacturer = UEManufacturer.UNKNOWN

    def __init__(self):
        self.linked_to_account = False
        self.client = Client()

    def set_host(self, ipv4: IPv4Address):
        self.ipv4 = IPv4Address(octets=ipv4.address, netmask=ipv4.netmask)
        self.logger.debug(
            f"assigning {str(ipv4)} to UE (imei: {self.imei}, imsi: {self.imsi})"
        )
        self._snmp = SNMP(str(self.ipv4))

    def __str__(self):
        return f"""
           [UE] sonar id: {self.sonar_id}
           IMEI: {self.imei} IMSI: {self.imsi} SIM index: {self.sim_index}
           MAC: {str(self.mac_address)} IP: {str(self.ipv4)}
           client: {str(self.client)}
            """

    def __repr__(self):
        return f"""
           [UE] sonar id: {self.sonar_id}
           IMEI: {self.imei} IMSI: {self.imsi} SIM index: {self.sim_index}
           MAC: {str(self.mac_address)} IP: {str(self.ipv4)}
           client: {str(self.client)}
            """
