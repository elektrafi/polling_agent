#!/usr/bin/env python3

import logging as _logging
from concurrent.futures import Future as _Future
from typing import Iterable as _Iterable
from threading import Thread as _Thread

from .sonar.api_connection import Sonar as _Sonar
from .genie_acs.api_connection import GenieACS as _GenieACS
from .raemis.api_connection import Raemis as _Raemis
from .raemis.event_listener import Listener as _Listener
from .sonar.ip_allocation import Allocator as _Allocator
from .snmp import Session as _Session
from .model.atoms import Item as _Item
from .model.structures import MergeSet as _MergeSet
from multiprocessing.pool import Pool as _Pool
from multiprocessing import Process as _Process
import asyncio as _asyncio


class PollingAgent:
    _logger = _logging.getLogger(__name__)
    _raemis: _Raemis
    _genis: _GenieACS
    _sonar: _Sonar
    _allocator: _Allocator
    _listener: _Listener
    _inventory: _MergeSet[_Item]
    _pool: _Pool
    _mainProc: _Thread

    def __init__(self):
        # self._mainProc = _Process(target=self._startup, daemon=False, name="main")
        # self._mainProc.start()
        self._mainProc = _Thread(target=self._startup, name="main", daemon=False)
        self._startup()

    def _startup(self):
        self._logger.info("starting polling agent thread")
        _logging.basicConfig(level=_logging.INFO)
        self._inventory = _MergeSet()
        self._raemis = _Raemis()
        self._genie = _GenieACS()
        self._sonar = _Sonar()
        self._pool = _Pool()
        self._starter()

<<<<<<< Updated upstream
    def _startup(self):
        inv = self._pipeline.start_fn(
            self._sonar.get_all_clients_and_assigned_inventory
        )
        inv.add_done_callback(self._assign_cb)
        subs = self._pipeline.start_fn_after_future(inv, self._raemis.get_subscribers)
        subs.add_done_callback(self._assign_cb)
        ips = self._pipeline.start_fn_after_future(subs, self._raemis.get_data_sessions)
        ips.add_done_callback(self._assign_cb)
        snmp = self._pipeline.start_fn_after_future(ips, self._update_snmp_info)
        self._pipeline.start_fn_after_future(
            snmp, lambda: self._logger.info("Finished startup process")
        )

    def _update_snmp_info(self) -> list[_Item]:
        def snmp_info(i: _Item):
            snmp = _Session(str(i.ipv4))
            i = snmp.get_item_values()
            self._inventory.add(i)
            return i

        return list(self._pipeline.map(snmp_info, self._inventory))

    def _assign_cb(self, l: _Future[list[_Item]]) -> None:
        while not l.done():
            pass
        if l.exception():
            self._logger.error(
                f"raemis encountered error getting subscribers: {l.exception()}"
            )
        result = l.result()
        if result is None:
            self._logger.error("raemis returned no subscribers")

        def fn(i: _Item) -> None:
            if i:
                try:
                    self._inventory.add(i)
                except:
                    self._logger.exception(f"exception updating {i}", stack_info=True)

        list(self._pipeline.map(fn, result))
=======
    def _starter(self):
        self._logger.info("starting initilization sync")
        inv = self._sonar.get_all_clients_and_assigned_inventory()
        inv = list(map(self._inventory.add, inv))
        subs = self._raemis.get_subscribers()
        subs = list(map(self._inventory.add, subs))
        ips = self._raemis.get_data_sessions()
        ips = list(map(self._inventory.add, ips))
        snmp = self._update_snmp_info()
        snmp = self._pool.map(self._inventory.add, snmp)
        self._logger.info("Finished startup process")

    def _update_snmp_info(self) -> _Iterable[_Item]:
        self._logger.info("getting SNMP info from devices")
        tasks: list[_Item] = []
        for item in self._inventory:
            tasks.append(_Session.get_item_values(item))
        return tasks
>>>>>>> Stashed changes
