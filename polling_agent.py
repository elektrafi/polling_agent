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
from .model.atoms import Item as _Item
from .model.structures import MergeSet as _MergeSet


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
        self._startup()

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
