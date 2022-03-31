#!/usr/bin/env python3
from model.network import MACAddress as _MACAddress, IMEI as _IMEI, IMSI as _IMSI
from model.atoms import Item as _Item, Model as _Model, Manufacturer as _Manufacturer
from typing import AsyncIterable as _AsyncIterable
import re as _re
import logging
import asyncio as _asyncio
from aiosnmp import Snmp as _Snmp, SnmpVarbind as _SnmpVarBind


class Session(object):
    _logger = logging.getLogger(__name__)

    @classmethod
    async def get_item_values(cls, i: _Item) -> _Item:
        ret = _Item()
        if not i.ipv4:
            return ret

        async with _Snmp(
            host=str(i.ipv4)[: str(i.ipv4).index("/")],
            community="public",
            timeout=5,
            retries=3,
        ) as snmp:
            cls._logger.info(f"getting SNMP info for IP {snmp.host}")
            info = (await cls._get_device_info(snmp)).strip().lower()
            print(info)
            t120_info = _re.compile(r"linux\s*[a-z0-9_]*\s*[-0-9\.]+uc\d")
            t123_info = _re.compile(r"linux\s*gdm\d{1,5}\s*[-0-9\.]+uc\d")
            bec69_info = _re.compile(
                r"(bec)?\s*((ridgewave)|(bec))?\s*((6[95]00)|(7000))((ael)|(-r21)|(\s*r28-g))?\s*4g/lte"
            )
            if _re.match(t123_info, info):
                ret = await cls._get_telrad_12300(snmp)
            if _re.match(t120_info, info):
                ret = await cls._get_telrad_12000(snmp)
            elif _re.match(bec69_info, info):
                ret = await cls._get_bec6900(snmp, info)
            else:
                cls._logger.error(f"no model type determined for {snmp.host}")
        cls._logger.info(f"returning {ret} for {snmp.host}")
        return ret

    @classmethod
    async def _get_device_info(cls, snmp: _Snmp) -> str:
        return await cls._snmp_get_value(snmp, ".1.3.6.1.2.1.1.1.0")

    @classmethod
    async def _get_telrad_12300(cls, snmp: _Snmp) -> _Item:
        ret = _Item()

        ret.model = _Model.T12300
        ret.manufacturer = _Manufacturer.TELRAD

        mac_num = await cls._snmp_search_bulk_regex(
            snmp, ".1.3.6.1.2.1.2.2.1.2", _re.compile(r"eth0")
        )
        if mac_num is None or not mac_num.oid:
            cls._logger.error(f"could not find the eth0 device for {snmp.host}")
            return ret
        mac_num = mac_num.oid.split(".")[-1]
        mac = await cls._snmp_get_value(snmp, f".1.3.6.1.2.1.2.2.1.6.{mac_num}")
        if mac:
            ret.mac_address = _MACAddress(mac)

        cls._logger.info(f"found {ret} as a Telrad 12300")
        return ret

    @classmethod
    async def _get_bec6900(cls, snmp: _Snmp, info: str) -> _Item:
        ret = _Item()
        if "6900" in info:
            ret.model = _Model.BEC6900
        if "6500" in info:
            ret.model = _Model.BEC6500
        if "7000" in info:
            ret.model = _Model.BEC7000
        ret.manufacturer = _Manufacturer.BEC
        mac_num = await cls._snmp_search_bulk_regex(
            snmp, ".1.3.6.1.2.1.2.2.1.2", _re.compile(r"eth0")
        )
        if mac_num is None or not mac_num.oid:
            cls._logger.error(f"could not find the eth0 device for {snmp.host}")
        else:
            mac_num = mac_num.oid.split(".")[-1]
            mac = await cls._snmp_get_value(snmp, f".1.3.6.1.2.1.2.2.1.6.{mac_num}")
            if mac:
                ret.mac_address = _MACAddress(mac)
        signals = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.4.0")
        if signals:
            for signal in signals.split(" "):
                parts = signal.split(":")
                if parts[0] == "RSRP":
                    ret.rsrp = parts[1]
                if parts[0] == "RSRQ":
                    ret.rsrq = parts[1]
                if parts[0] == "SINR":
                    ret.sinr = parts[1]
        eci = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.6.0")
        if eci:
            ret.eci = eci
        imei = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.8.0")
        if imei:
            ret.imei = _IMEI(imei)
        imsi = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.9.0")
        if imsi:
            ret.imsi = _IMSI(imsi)
        pci = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.7.0")
        if pci:
            ret.pci = pci
        bandwidth = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.11.0")
        if bandwidth:
            ret.bandwidth = _re.split(r":\s*", bandwidth)[-1]
        rssi = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.3.0")
        if rssi:
            ret.rssi = rssi
        rx_mcs = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.20.0")
        if rx_mcs:
            ret.rx_mcs = rx_mcs
        channel = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17453.4.1.17.0")
        if channel:
            ret.channel = channel

        cls._logger.info(f"found {ret} as a BEC Device")
        return ret

    @classmethod
    async def _get_telrad_12000(cls, snmp: _Snmp) -> _Item:
        ret = _Item()
        ret.model = _Model.T12000
        ret.manufacturer = _Manufacturer.TELRAD
        mac = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.3.13.0")
        if mac:
            ret.mac_address = _MACAddress(mac)
        imei = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.11.0")
        if imei:
            ret.imei = _IMEI(imei)
        imsi = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.13.0")
        if imsi:
            ret.imsi = _IMSI(imsi)
        serial = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.5.0")
        if serial:
            ret.serial_number = serial
        product = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.4.3.0")
        if product:
            ret.product_id = product
        rx_rate = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.14.0")
        if rx_rate:
            ret.rx_rate = rx_rate
        tx_rate = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.11.0")
        if tx_rate:
            ret.tx_rate = tx_rate
        tx_power = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.25.0")
        if tx_power:
            ret.tx_power = tx_power
        rsrp_list = cls._snmp_get_value_bulk(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.6")
        rsrp = 0
        cnt = 0
        async for r in rsrp_list:
            try:
                rsrp = float(r)
                cnt += 1
            except:
                cls._logger.exception(
                    f"error trying to parse rsrp {r} for telrae 12000"
                )
        if rsrp:
            ret.rsrp = str(rsrp / cnt)
        rsrq_list = cls._snmp_get_value_bulk(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.8")
        rsrq = 0
        cnt = 0
        async for r in rsrq_list:
            try:
                rsrq = float(r)
                cnt += 1
            except:
                cls._logger.exception(
                    f"error trying to parse rsrq {r} for telrae 12000"
                )
        if rsrq:
            ret.rsrq = str(rsrq / cnt)
        pci = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.18.0")
        if pci:
            ret.pci = pci
        eci = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.48.0")
        if eci:
            ret.eci = eci
        cell_id = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.17.0")
        if cell_id:
            ret.cell_id = cell_id
        full_cell_id = await cls._snmp_get_value(
            snmp, ".1.3.6.1.4.1.17713.20.2.1.2.36.0"
        )
        if full_cell_id:
            ret.full_cell_id = full_cell_id
        sinr_list = cls._snmp_get_value_bulk(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.32")
        sinr = 0
        cnt = 0
        async for r in sinr_list:
            try:
                sinr = float(r)
                cnt += 1
            except:
                cls._logger.exception(
                    f"error trying to parse sinr {r} for telrae 12000"
                )
        if sinr:
            ret.sinr = str(sinr / cnt)
        enb_id = await cls._snmp_get_value(snmp, ".1.3.6.1.4.1.17713.20.2.1.2.30.0")
        if enb_id:
            ret.enb_id = enb_id
        cls._logger.info(f"found {ret} as a Telrad 12000")
        return ret

    @classmethod
    async def _snmp_get_value_bulk(cls, snmp: _Snmp, oid: str) -> _AsyncIterable[str]:
        async for x in cls._snmp_get_bulk(snmp, oid):
            if not x:
                continue
            val = x.value
            if isinstance(val, bytes):
                val = val.decode()
            yield str(val)

    @classmethod
    async def _snmp_get_bulk(
        cls, snmp: _Snmp, oid: str
    ) -> _AsyncIterable[_SnmpVarBind]:
        try:
            for check in await snmp.bulk_walk(oid):
                if not isinstance(check, _SnmpVarBind):
                    continue
                try:
                    yield check
                except:
                    return
        except:
            cls._logger.exception(f"getting the oid group {oid} errored")

    @classmethod
    async def _snmp_search_bulk_value_regex(
        cls, snmp: _Snmp, oid: str, regex: _re.Pattern
    ) -> str:
        try:
            async for x in cls._snmp_get_value_bulk(snmp, oid):
                if x and _re.fullmatch(regex, x):
                    return x
        except:
            cls._logger.exception(f"snmp error", stack_info=True)
        return ""

    @classmethod
    async def _snmp_search_bulk_regex(
        cls, snmp: _Snmp, oid: str, regex: _re.Pattern
    ) -> _SnmpVarBind | None:
        try:
            async for x in cls._snmp_get_bulk(snmp, oid):
                if not x:
                    continue
                val = x.value
                if isinstance(val, bytes):
                    try:
                        val = val.decode()
                    except:
                        val = val.hex()
                if _re.fullmatch(regex, str(val)):
                    return x
        except:
            return None

    @classmethod
    async def _snmp_get_value(cls, snmp: _Snmp, oid: str) -> str:
        ret = await cls._snmp_get(snmp, oid)
        if not ret:
            return ""
        if isinstance(ret.value, bytes):
            try:
                ret = ret.value.decode()
            except:
                ret = ret.value.hex()
        else:
            ret = str(ret.value)
        return ret

    @classmethod
    async def _snmp_get(cls, snmp: _Snmp, oid: str) -> _SnmpVarBind | None:
        try:
            check = await snmp.get(oid)
            if isinstance(check, list):
                check = check[0]
            return check
        except:
            cls._logger.exception(f"errored getting oid {oid}")
