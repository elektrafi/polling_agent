#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import signal as _signal
import sys as _sys
import logging as _logging
from sonar.api_connection import Sonar as _Sonar
from raemis.api_connection import Raemis as _Raemis
from snmp import Session as _Session
from model.atoms import Item as _Item, Manufacturer, Model
from model.structures import MergeSet as _MergeSet
from asyncio import run as _run
from web_scraper.baicells import Baicells as _Baicells
from sonar.ip_allocation import PullAllocator as _PullAllocator
from multiprocessing.managers import SyncManager as _SyncManager
from threading import Event as _Event
from multiprocessing.dummy import DummyProcess as _Thread
from logging.handlers import RotatingFileHandler
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
            get_assignments=get_assignments,
            get_addresses=get_addresses,
            create=create,
            update=update,
            delete=delete,
            event=self._stop_event,
            base_list=base_list,
            delay=delay,
        )
        self._poll_thread = _Thread(target=self._allocator.poll, name="poller")
        self._poll_thread.start()

    def shutdown(self):
        self._stop_event.set()
        self._logger.info("sent stop event to poller")
        self._poll_thread.join()
        self._logger.info("joined ip poll thread")
        self._manager.shutdown()
        self._logger.info("shut down manager")

    def run_full_scan(self):
        self.get_base_inventory_information()
        self.get_subscriber_information()
        self.get_inventory_network_information()
        self.get_detailed_inventory_stats()

    def get_subscriber_information(self):
        subs = _run(_Raemis.get_subscribers())
        for item in subs:
            self._inventory.add(item)

    def get_inventory_network_information(self):
        ips = _run(_Raemis.get_data_sessions())
        for item in ips:
            self._inventory.add(item)
        web_tel = _run(_Telrad.get_items(self._inventory))
        for item in web_tel:
            if item:
                self._inventory.add(item)
        web = _run(_Baicells.get_items(self._inventory))
        for item in web:
            item.model = Model.OD06
            item.manufacturer = Manufacturer.BAICELLS
            self._inventory.add(item)

    def get_detailed_inventory_stats(self):
        snmp = _run(_Session.get_all_values(self._inventory))
        for item in snmp:
            self._inventory.add(item)

    def add_raemis_info_to_item_notes(self):
        _run(_Sonar.add_raemis_name_to_items(self._inventory))

    def try_to_match_items_to_accounts_by_name_guessing(self):
        _run(_Sonar.match_names_and_link(self._inventory))

    def create_missing_inventory_items(self):
        _run(_Sonar.create_missing(self._inventory))

    def update_inventory_item_information(self):
        _run(_Sonar.update_needed(self._inventory))

    def get_base_inventory_information(self):
        self._logger.info("starting inventory initilization")
        acct = _run(_Sonar.execute(_Sonar.get_all_clients_and_assigned_inventory))
        for item in acct:
            self._inventory.add(item)
        inv = _run(_Sonar.execute(_Sonar.get_inventory_items))
        for item in inv:
            self._inventory.add(item)


if __name__ == "__main__":

    def sig_handle(signum: int, _):
        import threading

        if threading.main_thread() == threading.current_thread():
            polling_agent.shutdown()
        _logging.warning(f"CAUGHT SIGNAL {_signal.strsignal(signum)} SHUTTING DOWN")
        _sys.exit(0)

    _signal.signal(_signal.SIGINT, sig_handle)
    _logging.basicConfig(
        level=_logging.INFO,
        format="""%(asctime)s %(levelname)s:: [%(threadName)s.%(name)s.%(funcName)s]: %(message)s""",
    )

    fh = RotatingFileHandler(
        filename="polling_agent_main.log",
        mode="w",
        maxBytes=102400,
        backupCount=4,
        delay=False,
    )
    fh.setFormatter(
        _logging.Formatter(
            """%(asctime)s %(levelname)s:: [%(threadName)s.%(name)s.%(funcName)s]: %(message)s"""
        )
    )
    _logging.root.addHandler(fh)
    polling_agent = PollingAgent()
    polling_agent.startup()
    polling_agent.get_base_inventory_information()
    polling_agent.run_allocator()
    polling_agent._poll_thread.join()
