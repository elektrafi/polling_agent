#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import aiohttp as _aiohttp
import time as _time
from model.network import (
    IPv4Address as _IPv4Address,
    IMEI as _IMEI,
    IMSI as _IMSI,
    MACAddress as _MACAddress,
)
from model.atoms import Item as _Item, Model as _Model, Manufacturer as _Manufacturer
import xml.etree.ElementTree as _ElementTree
import re as _re
import logging as _logging
from typing import Iterable as _Iterable
from asyncio import gather as _gather


class Telrad12300:
    _log = _logging.getLogger(__name__)

    @classmethod
    async def get_items(cls, items: _Iterable[_Item]):
        ret = list()
        for item in items:
            if item.ipv4 and item.imei and str(item.imei).startswith("86630"):
                info = cls.get_info(item.ipv4)
                cls._log.info(f"got web scraping info for a Telrad 12300: {info}")
                ret.append(info)
        return await _gather(*ret)

    @classmethod
    async def get_info(cls, ip: _IPv4Address):
        try:
            async with _aiohttp.ClientSession(
                base_url=f"https://{repr(ip)}:8080/",
                auto_decompress=True,
                trust_env=True,
            ) as session:
                i = _Item()
                i.model = _Model.T12300
                i.manufacturer = _Manufacturer.TELRAD
                i = await cls.lte_info(ip=ip, i=i, session=session)
                i = await cls.rate_info(ip=ip, i=i, session=session)
                i = await cls.mac_info(ip=ip, i=i, session=session)
                # i = await cls.radio_info(ip=ip, i=i, session=session)
                return i
        except:
            cls._log.exception(f"could not get telrad info for {ip}")

    @classmethod
    async def mac_info(cls, ip: _IPv4Address, i: _Item = _Item(), session=None):
        page = "/cgi-bin/cuslan.cgi"
        lan = {"Command": "GetLanStatus", "T": _time.time_ns() // 1_000}
        root = await cls.get_page(ip, page, lan, session)
        mac = root.find("mac")
        if mac is not None and mac.text is not None:
            i.mac_address = _MACAddress(mac.text)
        return i

    @classmethod
    async def rate_info(cls, ip: _IPv4Address, i: _Item = _Item(), session=None):
        page = "/cgi-bin/cusltestatus.cgi"
        rate = {"Command": "Thr", "T": _time.time_ns() // 1_000}
        root = await cls.get_page(ip, page, rate, session)
        rx_rate = root.find("RXRate")
        if rx_rate is not None and rx_rate.text is not None:
            i.rx_rate = rx_rate.text
        tx_rate = root.find("TXRate")
        if tx_rate is not None and tx_rate.text is not None:
            i.tx_rate = tx_rate.text
        max_rx_rate = root.find("MaxRXRate")
        if max_rx_rate is not None and max_rx_rate.text is not None:
            i.max_rx_rate = max_rx_rate.text
        max_tx_rate = root.find("MaxTXRate")
        if max_tx_rate is not None and max_tx_rate.text is not None:
            i.max_tx_rate = max_tx_rate.text
        return i

    @classmethod
    async def radio_info(cls, ip: _IPv4Address, i: _Item = _Item(), session=None):
        page = "/cgi-bin/cusradioinfo.cgi"
        radio = {"Command": "getRadioInfo", "T": str(int(_time.time() * 1000))}
        root = await cls.get_page(ip, page, radio, session)
        rsrp = root.find("RSRP")
        if rsrp is not None and rsrp.text is not None:
            parts = _re.split(r"\s*,\s*", rsrp.text)
            tot = 0
            for part in parts:
                try:
                    if float(part) != 0:
                        tot += float(part)
                except:
                    continue
            i.rsrp = str(tot) if tot != 0 else None
        rsrq = root.find("RSRQ")
        if rsrq is not None and rsrq.text is not None:
            parts = _re.split(r"\s*,\s*", rsrq.text)
            tot = 0
            for part in parts:
                try:
                    if float(part) != 0:
                        tot += float(part)
                except:
                    continue
            i.rsrq = str(tot) if tot != 0 else None
        earfcn = root.find("EARFCN")
        if earfcn is not None and earfcn.text is not None:
            i.earfcn = earfcn.text
        bandwidth = root.find("BandWidth")
        if bandwidth is not None and bandwidth.text is not None:
            i.bandwidth = bandwidth.text
        return i

    @classmethod
    async def lte_info(cls, ip: _IPv4Address, i: _Item = _Item(), session=None):
        data = {"Command": "Status", "T": _time.time_ns() // 1_000}
        page = "/cgi-bin/cusltestatus.cgi"
        root = await cls.get_page(ip, page, data, session)
        serial_number = root.find("SerialNumber")
        if serial_number is not None and serial_number.text is not None:
            i.serial_number = serial_number.text
        bandwidth = root.find("BandWidth")
        if bandwidth is not None and bandwidth.text is not None:
            i.bandwidth = bandwidth.text
        imsi = root.find("IMSI")
        if imsi is not None and imsi.text is not None:
            i.imsi = _IMSI(imsi.text)
        imei = root.find("IMEI")
        if imei is not None and imei.text is not None:
            i.imei = _IMEI(imei.text)
        cell_id = root.find("Cell_ID")
        if cell_id is not None and cell_id.text is not None:
            i.cell_id = cell_id.text
        pci = root.find("PCI")
        if pci is not None and pci.text is not None:
            i.pci = pci.text
        sinr = root.find("SINR")
        if sinr is not None and sinr.text is not None:
            i.sinr = sinr.text
        rssi = root.find("RSSI")
        if rssi is not None and rssi.text is not None:
            i.rssi = rssi.text
        ulmcs = root.find("ULMCS")
        if ulmcs is not None and ulmcs.text is not None:
            i.tx_mcs = ulmcs.text
        dlmcs = root.find("DLMCS")
        if dlmcs is not None and dlmcs.text is not None:
            i.rx_mcs = dlmcs.text
        return i

    @classmethod
    async def get_page(
        cls,
        host: _IPv4Address,
        page: str,
        data: dict[str, str | int],
        session: _aiohttp.ClientSession | None = None,
    ):
        if session is None:
            async with _aiohttp.ClientSession(
                base_url=f"https://{repr(host)}:8080/",
                auto_decompress=True,
                trust_env=True,
            ) as session:
                async with session.get(
                    url=page,
                    ssl=False,
                    params=data,
                ) as resp:
                    text = await resp.text()
                    parser = _ElementTree.XMLParser()
                    parser.feed(text)
                    build: _ElementTree.TreeBuilder = parser.target
                    root: _ElementTree.Element = build.close()
        else:
            async with session.get(
                url=page,
                ssl=False,
                params=data,
            ) as resp:
                text = await resp.text()
                parser = _ElementTree.XMLParser()
                parser.feed(text)
                build: _ElementTree.TreeBuilder = parser.target
                root: _ElementTree.Element = build.close()
        return root
