#!/usr/bin/env python3
from easysnmp import SNMPVariable as _SNMPVariable, Session as _Session
from .model.network import MACAddress as _MACAddress, IMEI as _IMEI, IMSI as _IMSI
from .model.atoms import Item as _Item, Model as _Model, Manufacturer as _Manufacturer
import re as _re
import logging


class Session(object):
    _logger = logging.getLogger(__name__)

    @classmethod
    def get_item_values(cls, i: _Item) -> _Item:
        ret = _Item()
        if not i.ipv4:
            return ret
        snmp = _Session(
            hostname=str(i.ipv4),
            version=2,
            community="public",
            timeout=5,
            retries=3,
        )

        cls._logger.info(f"getting SNMP info for IP {snmp.hostname}")
        info = cls._get_device_info(snmp).strip().lower()
        t120_info = _re.compile(r"linux\s*[a-z0-9_]*\s*[-0-9\.]+uc\d")
        t123_info = _re.compile(r"linux\s*gdm\d{1,5}\s*[-0-9\.]+uc\d")
        bec69_info = _re.compile(
            r"(bec)?\s*((ridgewave)|(bec))?\s*((6[95]00)|(7000))((ael)|(-r21)|(\s*r28-g))?\s*4g/lte"
        )
        if _re.match(t123_info, info):
            ret = cls._get_telrad_12300(snmp)
        if _re.match(t120_info, info):
            ret = cls._get_telrad_12000(snmp)
        elif _re.match(bec69_info, info):
            ret = cls._get_bec6900(snmp, info)
        else:
            cls._logger.error(f"no model type determined for {snmp.hostname}")
        cls._logger.info(f"returning {ret} for {snmp.hostname}")
        return ret

    @classmethod
    def _get_device_info(cls, snmp: _Session) -> str:
        return cls._snmp_get_value(snmp, ".1.3.6.1.2.1.1.1.0")

    @classmethod
    def _get_telrad_12300(cls, snmp: _Session) -> _Item:
        ret = _Item()

        ret.model = _Model.T12300
        ret.manufacturer = _Manufacturer.TELRAD

        mac_num = cls._snmp_search_bulk_regex(
            snmp, ".1.3.6.1.2.1.2.2.1.2", _re.compile(r"eth0")
        )
        if mac_num is None or not mac_num.oid:
            cls._logger.error(f"could not find the eth0 device for {snmp.hostname}")
            return ret
        mac_num = mac_num.oid.split(".")[-1]
        mac = cls._snmp_get_value(snmp, f".1.3.6.1.2.1.2.2.1.6.{mac_num}")
        if mac:
            ret.mac_address = _MACAddress(mac.encode().hex())

        cls._logger.info(f"found {ret} as a Telrad 12300")
        return ret

    @classmethod
    def _get_bec6900(cls, snmp: _Session, info: str) -> _Item:
        ret = _Item()
        if "6900" in info:
            ret.model = _Model.BEC6900
        if "6500" in info:
            ret.model = _Model.BEC6500
        if "7000" in info:
            ret.model = _Model.BEC7000
        ret.manufacturer = _Manufacturer.BEC
        mac_num = cls._snmp_search_bulk_regex(
            snmp, ".1.3.6.1.2.1.2.2.1.2", _re.compile(r"eth0")
        )
        if mac_num is None or not mac_num.oid:
            cls._logger.error(f"could not find the eth0 device for {snmp.hostname}")
        else:
            mac_num = mac_num.oid.split(".")[-1]
            mac = cls._snmp_get_value(snmp, f".1.3.6.1.2.1.2.2.1.6.{mac_num}")
            if mac:
                ret.mac_address = _MACAddress(mac.encode().hex())
        signals = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.4.0")
        if signals:
            for signal in signals.split(" "):
                parts = signal.split(":")
                if parts[0] == "RSRP":
                    ret.rsrp = parts[1]
                if parts[0] == "RSRQ":
                    ret.rsrq = parts[1]
                if parts[0] == "SINR":
                    ret.sinr = parts[1]
        eci = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.6.0")
        if eci:
            ret.eci = eci
        imei = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.8.0")
        if imei:
            ret.imei = _IMEI(imei)
        imsi = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.9.0")
        if imsi:
            ret.imsi = _IMSI(imsi)
        pci = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.7.0")
        if pci:
            ret.pci = pci
        bandwidth = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.11.0")
        if bandwidth:
            ret.bandwidth = _re.split(r":\s*", bandwidth)[-1]
        rssi = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.3.0")
        if rssi:
            ret.rssi = rssi
        rx_mcs = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.20.0")
        if rx_mcs:
            ret.rx_mcs = rx_mcs
        channel = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.17.0")
        if channel:
            ret.channel = channel

        cls._logger.info(f"found {ret} as a BEC Device")
        return ret

    @classmethod
    def _get_telrad_12000(cls, snmp: _Session) -> _Item:
        ret = _Item()
        ret.model = _Model.T12000
        ret.manufacturer = _Manufacturer.TELRAD
        mac = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.3.13.0")
        if mac:
            ret.mac_address = _MACAddress(mac)
        imei = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.11.0")
        if imei:
            ret.imei = _IMEI(imei)
        imsi = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.13.0")
        if imsi:
            ret.imsi = _IMSI(imsi)
        serial = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.5.0")
        if serial:
            ret.serial_number = serial
        product = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.3.0")
        if product:
            ret.product_id = product
        rx_rate = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.14.0")
        if rx_rate:
            ret.rx_rate = rx_rate
        tx_rate = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.11.0")
        if tx_rate:
            ret.tx_rate = tx_rate
        tx_power = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.25.0")
        if tx_power:
            ret.tx_power = tx_power
        rsrp_list = cls._snmp_get_value_bulk(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.6")
        rsrp = 0
        for r in rsrp_list:
            try:
                rsrp = float(r)
            except:
                cls._logger.exception(
                    f"error trying to parse rsrp {r} for telrae 12000"
                )
        if rsrp:
            ret.rsrp = str(rsrp / len(rsrp_list))
        rsrq_list = cls._snmp_get_value_bulk(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.8")
        rsrq = 0
        for r in rsrq_list:
            try:
                rsrq = float(r)
            except:
                cls._logger.exception(
                    f"error trying to parse rsrq {r} for telrae 12000"
                )
        if rsrq:
            ret.rsrq = str(rsrq / len(rsrq_list))
        pci = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.18.0")
        if pci:
            ret.pci = pci
        eci = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.48.0")
        if eci:
            ret.eci = eci
        cell_id = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.17.0")
        if cell_id:
            ret.cell_id = cell_id
        full_cell_id = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.36.0")
        if full_cell_id:
            ret.full_cell_id = full_cell_id
        sinr_list = cls._snmp_get_value_bulk(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.32")
        sinr = 0
        for r in sinr_list:
            try:
                sinr = float(r)
            except:
                cls._logger.exception(
                    f"error trying to parse sinr {r} for telrae 12000"
                )
        if sinr:
            ret.sinr = str(sinr / len(sinr_list))
        enb_id = cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.30.0")
        if enb_id:
            ret.enb_id = enb_id
        cls._logger.info(f"found {ret} as a Telrad 12000")
        return ret

    @classmethod
    def _snmp_get_value_bulk(cls, snmp: _Session, oid: str) -> list[str]:
        return list(x.value for x in cls._snmp_get_bulk(snmp, oid))

    @classmethod
    def _snmp_get_bulk(cls, snmp: _Session, oid: str) -> list[_SNMPVariable]:
        strs = list()
        if not cls._has_snmp:
            return strs
        try:
            s = snmp.bulkwalk(oid)
            for check in s:
                if isinstance(check, list):
                    check = check[0]
                if not isinstance(check, _SNMPVariable):
                    continue
                if not isinstance(check.value, str):
                    continue
                if not isinstance(check.snmp_type, str):
                    continue
                if check.snmp_type.lower() == "nosuchobject":
                    continue
                if check.snmp_type.lower() == "octetstr":
                    check.value = b"".join(
                        list(
                            map(
                                lambda x: (
                                    x.encode()
                                    if len(x.encode("utf")) == 1
                                    else x.encode()[1].to_bytes(1, "little")
                                ),
                                check.value,
                            )
                        )
                    ).decode()
                strs.append(check)
        except:
            cls._has_snmp = False
            cls._logger.exception(f"getting the oid group {oid} errored")
        return strs

    @classmethod
    def _snmp_search_bulk_value_regex(
        cls, snmp: _Session, oid: str, regex: _re.Pattern
    ):
        try:
            return next(
                x
                for x in cls._snmp_get_value_bulk(snmp, oid)
                if _re.fullmatch(regex, x)
            )
        except:
            return None

    @classmethod
    def _snmp_search_bulk_regex(cls, snmp: _Session, oid: str, regex: _re.Pattern):
        try:
            return next(
                x
                for x in cls._snmp_get_bulk(snmp, oid)
                if _re.fullmatch(regex, x.value)
            )
        except:
            return None

    @classmethod
    def _snmp_get_value(cls, snmp: _Session, oid: str) -> str:
        ret = cls._snmp_get(snmp, oid)
        if not ret:
            return ""
        return ret.value if ret.value and ret.value.lower() != "nosuchobject" else ""

    @classmethod
    def _snmp_get(cls, snmp: _Session, oid: str) -> _SNMPVariable | None:
        if not cls._has_snmp:
            return
        try:
            check = snmp.get(oid)
            if isinstance(check, list):
                check = check[0]
            if not isinstance(check, _SNMPVariable):
                return
            if not isinstance(check.value, str):
                return
            if not isinstance(check.snmp_type, str):
                return
            if check.snmp_type.lower() == "nosuchobject":
                return
            if check.snmp_type.lower() == "octetstr":
                check.value = b"".join(
                    list(
                        map(
                            lambda x: (
                                x.encode()
                                if len(x.encode("utf")) == 1
                                else x.encode()[1].to_bytes(1, "little")
                            ),
                            check.value,
                        )
                    )
                ).decode()
            return check
        except:
            cls._has_snmp = False
            cls._logger.exception(f"errored getting oid {oid}")
