#!/usr/bin/env python3

from collections import UserString as _UserString
from dataclasses import dataclass as _dc
import logging
from typing import Any as _Any, FrozenSet as _FrozenSet
from typing_extensions import Self as _Self
from enum import Enum as _Enum
from .network import (
    IPv4Address as _IPv4Address,
    MACAddress as _MACAddress,
    IMEI as _IMEI,
    IMSI as _IMSI,
)


class Manufacturer(_Enum):
    BAICELLS = "Baicells"
    TELRAD = "Telrad"
    BEC = "BEC"
    NETGEAR = "Netgear"
    UNKNOWN = "Unknown"


class Model(_Enum):
    OD06 = "OD06"
    BEC6900 = "RidgeWave 6900"
    BEC6500 = "RidgeWave 6500"
    BEC7000 = "RidgeWave 7000"
    T12000 = "12000 Series"
    T12300 = "12300 Series"
    WAC104 = "WAC104 with ElektraFi-RT Firmware"
    UNKNOWN = "Unknown Device Type"


_IPType = type(_IPv4Address)


class Name(_UserString):
    def __init__(self, seq: object) -> None:
        if seq is None:
            s = ""
        s = str(seq)
        s = Name._repl(s)
        super().__init__(s)

    def __eq__(self, string: object) -> bool:
        if not (isinstance(string, Name) or isinstance(string, str)):
            return False
        if isinstance(string, Name):
            s = string.data
        else:
            s = string
        s = Name._repl(str(s))
        return all(map(lambda x: "&" in x or x in self.data, s.split(" ")))

    def __hash__(self) -> int:
        return hash(self.data)

    def __repr__(self) -> str:
        return str(self.data)

    @classmethod
    def _repl(cls, s: str) -> str:
        import re

        s = re.sub(r"\s+", r" ", s)
        s = re.sub(r"(.*)\s+(&|and)\s+(.*)", r"\1 & \2", s)
        s = re.sub(r"(.*)\s?,\s?(.*)", r"\2 \1", s)
        return s


@_dc
class Address:
    sonar_id: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    zip_code: str | None = None

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Address):
            return False
        return (
            (
                bool(__o.zip_code)
                and bool(self.zip_code)
                and __o.zip_code == self.zip_code
            )
            and (bool(__o.city) and bool(self.city) and __o.city == self.city)
            and (bool(__o.line1) and bool(self.line1) and __o.line1 == self.line1)
        ) or (
            bool(__o.sonar_id) and bool(self.sonar_id) and __o.sonar_id == self.sonar_id
        )

    def __hash__(self) -> int:
        return hash(self.sonar_id if self.sonar_id else str(self))

    def __str__(self) -> str:
        return f'<<Address: {"(id: " + self.sonar_id + ") " if self.sonar_id else ""}{self.line1}{" " + self.line2 if self.line2 else ""}; {self.city}, {self.zip_code}>>'

    def __repr__(self) -> str:
        return "{id: " + str(self.sonar_id) + "}" if self.sonar_id else str(self)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Address):
            return False
        return (
            self.sonar_id == __o.sonar_id
            if self.sonar_id and __o.sonar_id
            else str(self) == str(__o)
        )


@_dc
class Account:
    logger = logging.getLogger(__name__)
    sonar_id: str | None = None
    name: Name | None = None
    address: Address | None = None

    def __init__(self, name: Name | None = None):
        self.name = name

    def __str__(self) -> str:
        return f'||[Account] {"(id: "+self.sonar_id+") " if self.sonar_id else ""}{str(self.name) if self.name else ""}||'

    def __repr__(self) -> str:
        return f'{{{"id: " + str(self.sonar_id) + ", " if self.sonar_id else ""}{"name: " + self.name + ", " if self.name else ""}{"address: " + repr(self.address) if self.address else ""}}}'

    def __hash__(self):
        return hash(self.key)

    @property
    def key(self):
        ret = []
        if self.sonar_id:
            ret.append(self.sonar_id)
        if self.name:
            ret.append(self.name)
        return frozenset(ret)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Account) or len(self.key) == 0 or len(__o.key) == 0:
            return False
        return any(map(lambda x: x in self.key, __o.key))

    @classmethod
    def from_sonar(cls, d: dict[str, _Any]) -> _Self:
        ret = cls.__new__(cls)
        cls.logger.info(f"creating account/address record with {d}")
        if "id" not in d or not d["id"]:
            cls.logger.error("no sonar id for client")
        else:
            ret.sonar_id = d["id"]
        if "name" not in d or not d["name"]:
            cls.logger.error(
                f'no name attached to account {ret.sonar_id if ret.sonar_id else "UNKNOWN"}'
            )
        else:
            ret.name = d["name"]
        if "addresses" in d and d["addresses"]["entities"]:
            for address in d["addresses"]["entities"]:
                if not ret.address:
                    ret.address = Address()

                if "id" not in address or not address["id"]:
                    cls.logger.error(
                        f"no sonar id for address for account {ret.sonar_id}"
                    )
                else:
                    ret.address.sonar_id = address["id"]

                if "line1" not in address or not address["line1"]:
                    cls.logger.error(
                        f"no sonar line1 for address for account {ret.sonar_id}"
                    )
                else:
                    ret.address.line1 = address["line1"]

                if "line2" not in address or not address["line2"]:
                    pass
                else:
                    ret.address.line2 = address["line2"]

                if "city" not in address or not address["city"]:
                    cls.logger.error(
                        f"no sonar city for address for account {ret.sonar_id}"
                    )
                else:
                    ret.address.city = address["city"]

                if "zip" not in address or not address["zip"]:
                    cls.logger.error(
                        f"no sonar zip for address for account {ret.sonar_id}"
                    )
                else:
                    ret.address.zip_code = address["zip"]
        else:
            cls.logger.error(
                f"account {ret.sonar_id} for {ret.name} has no servicable address"
            )
        cls.logger.debug(f"created account:\n{ret}")
        return ret


@_dc
class Item(object):
    logger = logging.getLogger(__name__)
    mac_address: _MACAddress | None = None
    serial_number: str | None = None
    product_id: str | None = None
    sonar_id: str | None = None
    linked_to_account: bool = False
    info: str | None = None
    imei: _IMEI | None = None
    imsi: _IMSI | None = None
    _raemis_id: str | None = None
    pci: str | None = None
    enb_id: str | None = None
    channel: str | None = None
    cell_id: str | None = None
    full_cell_id: str | None = None
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
    model: Model = Model.UNKNOWN
    manufacturer: Manufacturer = Manufacturer.UNKNOWN
    _account: Account | None = None
    _ipv4: _IPType | None = None

    @property
    def ipv4(self) -> _IPType | None:
        return self._ipv4

    @ipv4.setter
    def ipv4(self, __o: object) -> None:
        if not isinstance(__o, _IPv4Address) and not isinstance(__o, str):
            return
        if isinstance(__o, str):
            self._ipv4 = _IPv4Address(address=__o)
        if isinstance(__o, _IPv4Address):
            self._ipv4 = __o

    @property
    def account(self) -> Account | None:
        return self._account

    @account.setter
    def account(self, __o: object) -> None:
        if not isinstance(__o, Account):
            return
        if not self._account:
            self._account = __o
            return
        if self._account != __o:
            self.logger.error(
                f"item has account {self._account} and trying to assign {__o}, but that does not match and it should"
            )
            raise ValueError
        for k, v in __o.__dict__.items():
            setattr(self._account, k, v)

    @property
    def key(self) -> _FrozenSet[Account | _MACAddress | _IPv4Address | _IMEI | _IMSI]:
        ret = []
        if self.account:
            ret.append(self.account)
        if self.sonar_id:
            ret.append(self.sonar_id)
        if self.mac_address:
            ret.append(self.mac_address)
        if self.imei:
            ret.append(self.imei)
        if self.imsi:
            ret.append(self.imsi)
        return frozenset(ret)

    def __hash__(self) -> int:
        return hash(self.key)

    def __init__(self):
        self.linked_to_account = False

    def __str__(self):
        return f"Inventory item: {self.key}"

    def __repr__(self):
        return str(self.key)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Item) or len(self.key) == 0 or len(__o.key) == 0:
            return False
        return any(map(lambda x: x in self.key, __o.key))

    @classmethod
    def from_sonar(cls, d: dict[str, _Any]) -> _Self:
        ret = cls.__new__(cls)
        cls.logger.info(f"creating new inventory item record for {d}")
        if "id" not in d or not d["id"]:
            cls.logger.error("no sonar id for this inventory item")
        else:
            ret.sonar_id = d["id"]
        if (
            "inventory_model_field_data" in d
            and d["inventory_model_field_data"]["entities"]
        ):
            for field in d["inventory_model_field_data"]["entities"]:
                if (
                    "inventory_model_field" not in field
                    or not field["inventory_model_field"]["name"]
                ):
                    cls.logger.error(
                        f'no field name for data {field["value"] if "value" in field else "UNKNOWN"}, skipping'
                    )
                    continue
                name = field["inventory_model_field"]["name"].strip().lower()

                if "value" not in field or not field["value"]:
                    cls.logger.error(f"field {name} has no value, skipping")
                    continue
                value = field["value"].strip().lower()
                if "imei" in name:
                    ret.imei = _IMEI(value)
                elif "imsi" in name:
                    ret.imsi = _IMSI(value)
                elif "mac" in name:
                    ret.mac_address = _MACAddress(value)
                elif "product" in name:
                    ret.product_id = value
                elif "serial" in name:
                    ret.serial_number = value
                elif "name" in name:
                    ret.info = value
                else:
                    cls.logger.warn(f"unknown type of data for field: {name}")
        else:
            cls.logger.warn(
                f'no field data for inventory item {ret.sonar_id if ret.sonar_id else "UNKNOWN"}'
            )
        if "inventory_model" not in d or not d["inventory_model"]["name"]:
            cls.logger.error(
                f'no model data for inventory item {ret.sonar_id if ret.sonar_id else "UNKNOWN"}'
            )
        else:
            model = d["inventory_model"]["name"].strip().lower()
            if "od06" in model:
                ret.model = Model.OD06
                ret.manufacturer = Manufacturer.BAICELLS
            elif "7000" in model:
                ret.model = Model.BEC7000
                ret.manufacturer = Manufacturer.BEC
            elif "6900" in model:
                ret.model = Model.BEC6900
                ret.manufacturer = Manufacturer.BEC
            elif "6500" in model:
                ret.model = Model.BEC6500
                ret.manufacturer = Manufacturer.BEC
            elif "12300" in model:
                ret.model = Model.T12300
                ret.manufacturer = Manufacturer.TELRAD
            elif "12000" in model:
                ret.model = Model.T12000
                ret.manufacturer = Manufacturer.TELRAD
            else:
                cls.logger.error(f"unknown model: {model}")
        cls.logger.debug(f"created new inventory item:\n{ret}")
        return ret


def from_sonar(d: dict[str, _Any]) -> list[Item]:
    items: list[Item] = list()
    if "addresses" in d and d["addresses"]["entities"]:
        address = d["addresses"]["entities"][0]
        if "inventory_items" in address and address["inventory_items"]["entities"]:
            for item in address["inventory_items"]["entities"]:
                i = Item.from_sonar(item)
                i.account = Account.from_sonar(d)
                items.append(i)
    return items
