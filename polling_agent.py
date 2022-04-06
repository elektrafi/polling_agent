#!/usr/bin/env python3

import multiprocessing
import signal
import sys
import logging as _logging
from functools import partial as _partial
from time import get_clock_info
import time
from model.network import IPv4Address

from sonar.api_connection import Sonar as _Sonar
from raemis.api_connection import Raemis as _Raemis
from snmp import Session as _Session
from model.atoms import Item as _Item, Manufacturer, Model
from model.structures import MergeSet as _MergeSet
from asyncio import run as _run
import asyncio as _asyncio
from web_scraper.baicells import Baicells as _Baicells
from sonar.ip_allocation import Attachment, PullAllocator as _PullAllocator
from multiprocessing.managers import SyncManager as _SyncManager
from multiprocessing import set_start_method as _mp_method, get_logger
from typing import Iterable as _Iterable, Coroutine as _Coroutine, Any as _Any
from threading import Event as _Event
from multiprocessing.dummy import DummyProcess as _Thread
from queue import Queue as _Queue
import queue as _queue
import multiprocessing.queues as _queues
from sys import stdout as _stdout
from logging import StreamHandler as _Handler, Formatter as _Formatter
from web_scraper.bec import BECWebEmulator
from model.network import MACAddress
from web_scraper.telrad import Telrad12300 as _Telrad


class PollingAgent:
    _logger = _logging.getLogger(__name__)
    _inventory: _MergeSet[_Item]
    _allocator: _PullAllocator
    _manager: _SyncManager
    _stop_event: _Event

    def startup(self):
        self._logger.info("starting polling agent thread")
        self._inventory = _MergeSet()
        self._manager = _SyncManager()
        self._manager.start()
        self._stop_event = self._manager.Event()

    def run_allocator(self):
        create = _Sonar.create_ip_assignment
        update = _Sonar.update_ip_assignment
        delete = _Sonar.delete_ip_assignment
        get_assignments = _Sonar.get_ip_address_assignments
        get_addresses = _Raemis.get_data_sessions
        base_list: list[_Item] = self._manager.list(list(self._inventory))
        delay = 1 * 60

        self._allocator = _PullAllocator(
            self._manager,
            get_assignments=get_assignments,
            get_addresses=get_addresses,
            create=create,
            update=update,
            delete=delete,
            event=self._stop_event,
            base_list=base_list,
            delay=delay,
        )
        self._poll_thread = _Thread(target=self._allocator.new_poll, name="poller")
        self._poll_thread.start()

    def shutdown(self):
        self._stop_event.set()
        self._logger.info("sent stop event to poller")
        self._poll_thread.join()
        self._logger.info("joined ip poll thread")
        self._manager.shutdown()
        self._logger.info("shut down manager")

    def run_pickup(self):
        self._logger.info("starting initilization sync")
        acct = _run(_Sonar.execute(_Sonar.get_all_clients_and_assigned_inventory))
        for item in acct:
            self._inventory.add(item)
        inv = _run(_Sonar.execute(_Sonar.get_inventory_items))
        for item in inv:
            self._inventory.add(item)
        # subs = _run(_Raemis.get_subscribers())
        # for item in subs:
        #    self._inventory.add(item)
        # ips = _run(_Raemis.get_data_sessions())
        # for item in ips:
        # self._inventory.add(item)
        # snmp = _run(_Session.get_all_values(self._inventory))
        # for item in snmp:
        #    self._inventory.add(item)
        # web_tel = _run(_Telrad.get_items(self._inventory))
        # for item in web_tel:
        #    if item:
        #        self._inventory.add(item)
        # web = _run(_Baicells.get_items(self._inventory))
        # for item in web:
        #    item.model = Model.OD06
        #    item.manufacturer = Manufacturer.BAICELLS
        #    self._inventory.add(item)
        # _ = _run(_Sonar.create_missing(self._inventory))
        # _ = _run(_Sonar.update_needed(self._inventory))
        # linked = _run(_Sonar.add_raemis_name_to_items(self._inventory))
        # _ = _run(_Sonar.match_names_and_link(self._inventory))
        # self.report(linked)


if __name__ == "__main__":

    def sig_handle(signum: int, _):
        import threading

        if threading.main_thread() == threading.current_thread():
            polling_agent.shutdown()
        _logging.warning(f"CAUGHT SIGNAL {signal.strsignal(signum)} SHUTTING DOWN")
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handle)
    _logging.basicConfig(
        level=_logging.INFO,
        format="""%(asctime)s %(levelname)s:: [%(threadName)s.%(name)s.%(funcName)s]: %(message)s""",
    )

    fh = _logging.FileHandler("polling_agent_main.log", mode="w")
    fh.setFormatter(
        _logging.Formatter(
            """%(asctime)s %(levelname)s:: [%(threadName)s.%(name)s.%(funcName)s]: %(message)s"""
        )
    )
    _logging.root.addHandler(fh)
    polling_agent = PollingAgent()
    polling_agent.startup()
    polling_agent.run_pickup()
    polling_agent.run_allocator()
    # polling_agent.shutdown()
    polling_agent._poll_thread.join()
