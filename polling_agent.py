#!/usr/bin/env python3

import logging as _logging
from concurrent.futures import Future as _Future

from .pipeline import Pipeline as _Pipeline
from .sonar.api_connection import Sonar as _Sonar
from .genie_acs.api_connection import GenieACS as _GenieACS
from .raemis.api_connection import Raemis as _Raemis
from .raemis.event_listener import Listener as _Listener
from .sonar.ip_allocation import Allocator as _Allocator
from .model.atoms import Item as _Item, Account as _Account
from .model.structures import MergeSet as _MergeSet

from typing import TypeVar as _TypeVar

_T = _TypeVar("_T", _Account, _Item)


class PollingAgent:
    logger = _logging.getLogger(__name__)
    raemis: _Raemis
    genis: _GenieACS
    sonar: _Sonar
    allocator: _Allocator
    listener: _Listener
    inventory: _MergeSet[_Item]
    pipeline: _Pipeline
    accounts: _MergeSet[_Account]
    mapped: dict[_Account, _Item]

    def __init__(self):
        self.logger.info("starting polling agent")
        self.inventory = _MergeSet()
        self.accounts = _MergeSet()
        self.pipeline = _Pipeline()
        self.raemis = _Raemis()
        self.genie = _GenieACS()
        self.sonar = _Sonar()
        self.mapped = {}
        # self.listener = _Listener()
        # self.allocator = _Allocator(self.__get_item_by_imsi)
        # self.allocator.start_loop()
        self.__startup()

    def __startup(self):
        inv = self.pipeline.start_fn(self.sonar.get_inventory_items)
        inv.add_done_callback(self.__assign_cb)
        acct = self.pipeline.start_fn(self.sonar.get_accounts)
        acct.add_done_callback(self.__assign_cb)
        subs = self.pipeline.start_fn_after_futures_list(
            [inv, acct], self.raemis.get_subscribers
        )
        subs.add_done_callback(self._assign_zip_cb)

    def __assign_cb(self, l: _Future[list[_T] | None]) -> None:
        while not l.done():
            pass
        if l.exception():
            self.logger.error(
                f"sonar errored while getting inventory items with: {l.exception()}"
            )
            return
        result = l.result()
        if result is None:
            self.logger.error("sonar returned no inventory items")
            return

        def fn(one: _T):
            if isinstance(one, _Account):
                self.accounts.add(one)
            if isinstance(one, _Item):
                self.inventory.add(one)

        self.pipeline.map(fn, result)

    def _assign_zip_cb(
        self, l: _Future[list[tuple[_Item | None, _Account | None]]]
    ) -> None:
        while not l.done():
            pass
        if l.exception():
            self.logger.error(
                f"raemis encountered error getting subscribers: {l.exception()}"
            )
        result = l.result()
        if result is None:
            self.logger.error("raemis returned no subscribers")
            return

        def fn(t: tuple[_Item | None, _Account | None]):
            i, a = t
            if a:
                a = self.accounts.add(a)
            if i:
                i = self.inventory.add(i)
            if i and a:
                self.logger.info(f"mapping account {a} to item {i}")
                self.mapped[a] = i

        self.pipeline.map(fn, result)
