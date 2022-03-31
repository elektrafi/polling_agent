#!/usr/bin/env python3

import logging as _logging
from concurrent.futures import Future as _Future

from .pipeline import Pipeline as _Pipeline
from .sonar.api_connection import Sonar as _Sonar
from .genie_acs.api_connection import GenieACS as _GenieACS
from .raemis.api_connection import Raemis as _Raemis
from .raemis.event_listener import Listener as _Listener
from .sonar.ip_allocation import Allocator as _Allocator
from .snmp import Session as _Session
from .model.atoms import Item as _Item, Manufacturer as _Manufacturer
from .model.structures import MergeSet as _MergeSet
from multiprocessing.pool import Pool as _Pool
from multiprocessing import Process as _Process
import asyncio as _asyncio
from asyncio import run as _run

_exec = _Pool()


class PollingAgent:
    _logger = _logging.getLogger(__name__)
    _raemis: _Raemis
    _genis: _GenieACS
    _sonar: _Sonar
    _allocator: _Allocator
    _listener: _Listener
    _inventory: _MergeSet[_Item]
    _pipeline: _Pipeline

    def __init__(self):
        self._logger.info("starting polling agent")
        self._inventory = _MergeSet()
        self._pipeline = _Pipeline()
        self._raemis = _Raemis()
        self._genie = _GenieACS()
        self._sonar = _Sonar()
        # self.listener = _Listener()
        # self.allocator = _Allocator(self.__get_item_by_imsi)
        # self.allocator.start_loop()
        self._starter()

    def _starter(self):
        self._logger.info("starting initilization sync")
        inv = _run(
            self._sonar.execute(self._sonar.get_all_clients_and_assigned_inventory)
        )
        inv = list(_exec.map(self._inventory.add, inv, chunksize=125))
        subs = _run(self._raemis.get_subscribers())
        subs = list(_exec.map(self._inventory.add, subs, chunksize=150))
        ips = _run(self._raemis.get_data_sessions())
        ips = list(_exec.map(self._inventory.add, ips))
        snmp = self._update_snmp_info()
        snmp = self._pool.map(self._inventory.add, snmp)
        self._logger.info("Finished startup process")

    def _update_snmp_info(self) -> _Iterable[_Item]:
        self._logger.info("getting SNMP info from devices")
        tasks: list[_Item] = []
        for item in self._inventory:
            if item.manufacturer != _Manufacturer.BAICELLS:
                _Session.get_item_values()

        return tasks
