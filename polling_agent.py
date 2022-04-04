#!/usr/bin/env python3

import multiprocessing
import signal
import sys
import logging as _logging
from functools import partial as _partial
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
from typing import Iterable as _Iterable
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
    _queue: _Queue

    def startup(self):
        self._logger.info("starting polling agent thread")
        self._inventory = _MergeSet()
        self._manager = _SyncManager()
        self._manager.start()

        self._stop_event = self._manager.Event()

        self._queue = self._manager.Queue()

    def run_raemis_poller(self, delay):
        self._raemis_poll_thread = _Thread(target=self.poll_raemis, args=[delay])
        self._raemis_poll_thread.start()

    def run_allocator(self):
        create = _Sonar.create_ip_assignment
        update = _Sonar.update_ip_assignment
        self._allocator = _PullAllocator(
            self._manager, create, update, self._stop_event, self._queue
        )
        self._poll_thread = _Thread(target=self._allocator.poll, name="poller")
        self._poll_thread.start()

    def queue_ips(self, items: _Iterable[_Item]):
        for item in items:
            new = self._inventory.add(item)
            attach = Attachment.item_to_attachment(new)
            if new.mac_address and new.ipv4 and new.sonar_id:
                self._queue.put(attach)
                self._logger.debug(f"sent {attach} to the queue")

    def poll_raemis(self, delay):
        while not self._stop_event.is_set():
            try:
                time.sleep(60 * delay)
                ips = _run(_Raemis.get_data_sessions())
                self._logger.info(f"queueing {len(list(ips))} ip addresses to update")
                self.queue_ips(ips)
            except:
                self._logger.exception(f"raemis connection threw an error")
                continue

    def shutdown(self):
        import threading

        if self._raemis_poll_thread != threading.current_thread():
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except:
                    self._logger.error("couldnt empty queue")
            self._stop_event.set()
            self._logger.info("sent stop event to poller")
            self._poll_thread.join()
            self._logger.info("joined ip poll thread")
            self._raemis_poll_thread.join()
            self._logger.info("joined raemis poll thread")
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
        ips = _run(_Raemis.get_data_sessions())
        for item in ips:
            self._inventory.add(item)
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
        self.queue_ips(self._inventory)

    def report(self, inv):
        import pprint

        self._logger.info(f"added note to {len(inv)} accounts")


if __name__ == "__main__":

    import time

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
    polling_agent.run_allocator()
    polling_agent.run_pickup()
    # polling_agent.shutdown()
    polling_agent.run_raemis_poller(5)
    polling_agent._poll_thread.join()
    polling_agent._raemis_poll_thread.join()
