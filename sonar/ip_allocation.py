#!/usr/bin/env python3

from multiprocessing import Queue as _Queue, Process as _Process, Event as _Event
from typing import Callable as _Callable, Any as _Any
from typing_extensions import Self as _Self
from .api_connection import Sonar as _Sonar

from ..model.atoms import Item as _Item
from ..model.network import IPv4Address as _IPv4Address
import time as _time
import logging as _logging


class Attachment:
    _imsi: str
    _timestamp: _time.struct_time | None
    _address: _IPv4Address | None

    def __init__(self, i, t=None, a=None):
        self._imsi = i
        self._timestamp = t
        self._address = a


class Allocator(object):
    pending_allocations: _Queue
    _logger = _logging.getLogger(__name__)
    _loop_process: _Process
    _stop_event: _Any
    _ue_callback: _Callable[[str], _Item | None]
    _sonar: _Sonar
    _api_key: str
    _inst: _Self | None = None

    def __init__(self, ue_callback: _Callable[[str], _Item | None]):
        self._logger.info("creating IP address allocator thread")
        self._sonar = _Sonar()
        self._api_key = self._sonar._sonar_api_key
        self._ue_callback = ue_callback
        self.pending_allocations = _Queue()
        self._stop_event = _Event()
        self._loop_process = _Process(
            name="processing_loop",
            target=self._start_processing_loop,
            args=(self._stop_event, self._ue_callback),
        )
        self._loop_process.daemon = True

    def __new__(cls: type[_Self], *args, **kwargs) -> _Self:
        if not cls._inst:
            cls._inst = super(Allocator, cls).__new__(cls)
        return cls._inst

    def start_loop(self):
        self._logger.info("starting ip address allocator loop")
        self._loop_process.start()

    def add_pending_allocation(self, allocation: Attachment) -> None:
        self.pending_allocations.put(allocation)
        self._logger.info(f"added {allocation} to pending allocations queue")

    def __del__(self):
        self._logger.info("shutting down ip allocator")
        self._stop_event.set()
        self._loop_process.join()

    def _start_processing_loop(
        self, stop_event: _Any, get_item: _Callable[[str], _Item | None]
    ):
        self._logger.info("allocator loop started")
        while True:
            if stop_event.is_set():
                self._logger.info("stopping processing loop child process")
                break
            alloc = self.pending_allocations.get()
            if not alloc.imsi:
                self._logger.error(
                    f"imsi from raemis update were malformed (imsi: {alloc.imsi})"
                )
                continue
            ue = get_item(alloc.imsi)
            if ue is None:
                self._logger.error(
                    f"could not match ue to imsi: {alloc.imsi}, skipping"
                )
                continue
            self._logger.debug(f"imsi: {alloc.imsi} matched Item: {ue}")
            ue.ipv4 = alloc.address
            self._update_allocation(ue)

    def _update_allocation(self, item: _Item):
        url = "https://elektrafi.sonar.software/api/dhcp"
        data = {
            "mac_address": str(item.mac_address),
            "remote_id": str(item.imsi),
            "expired": 0 if item.ipv4 else 1,
            "api_key": self._api_key,
        }
        if item.ipv4:
            data["ip_address"] = str(item.ipv4)
        resp = None
        try:
            self._logger.info(
                f"WOULD BE SENDING!!!!!!\n\t\t<< url: {url} data: {data} >>>"
            )
            # resp = requests.get(url, verify=False, params=data)
        except:
            self._logger.error(f"Could not update Item IP address in Sonar: {item}")
        return resp
