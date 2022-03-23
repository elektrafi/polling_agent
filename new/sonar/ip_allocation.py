#!/usr/bin/env python3

from multiprocessing import Queue, Process, Event
from typing import Callable, Any
import requests
from typing_extensions import Self
from ..sonar.api_connection import Sonar

from ..model.ue import UE
from ..model.ip_address import IPv4Address
import time
import logging


class Attachment:
    imsi: str
    timestamp: time.struct_time | None
    address: IPv4Address | None

    def __init__(self, i, t=None, a=None):
        self.imsi = i
        self.timestamp = t
        self.address = a


class Allocator(object):
    pending_allocations: Queue
    logger = logging.getLogger(__name__)
    __loop_process: Process
    __stop_event: Any
    __ue_callback: Callable[[str], UE | None]
    __sonar: Sonar
    __api_key: str
    inst: Self | None = None

    def __init__(self, ue_callback: Callable[[str], UE | None]):
        self.logger.info("creating IP address allocator thread")
        self.__sonar = Sonar()
        self.__api_key = self.__sonar.sonar_api_key
        self.__ue_callback = ue_callback
        self.pending_allocations = Queue()
        self.__stop_event = Event()
        self.__loop_process = Process(
            name="processing_loop",
            target=self.__start_processing_loop,
            args=(self.__stop_event, self.__ue_callback),
        )
        self.__loop_process.daemon = True

    def __new__(cls: type[Self], *args, **kwargs) -> Self:
        if not cls.inst:
            cls.inst = object.__new__(cls, *args, **kwargs)
        return cls.inst

    def start_loop(self):
        self.logger.info("starting ip address allocator loop")
        self.__loop_process.start()

    def add_pending_allocation(self, allocation: Attachment) -> None:
        self.pending_allocations.put(allocation)
        self.logger.info(f"added {allocation} to pending allocations queue")

    def __del__(self):
        self.logger.info("shutting down ip allocator")
        self.__stop_event.set()
        self.__loop_process.join()

    def __start_processing_loop(
        self, stop_event: Any, get_ue: Callable[[str], UE | None]
    ):
        self.logger.info("allocator loop started")
        while True:
            if stop_event.is_set():
                self.logger.info("stopping processing loop child process")
                break
            alloc = self.pending_allocations.get()
            if not alloc.imsi:
                self.logger.error(
                    f"imsi from raemis update were malformed (imsi: {alloc.imsi})"
                )
                continue
            ue = get_ue(alloc.imsi)
            if ue is None:
                self.logger.error(f"could not match ue to imsi: {alloc.imsi}, skipping")
                continue
            self.logger.debug(f"imsi: {alloc.imsi} matched UE: {ue}")
            ue.ipv4 = alloc.address
            self.__update_allocation(ue)

    def __update_allocation(self, ue: UE):
        url = "https://elektrafi.sonar.software/api/dhcp"
        data = {
            "mac_address": str(ue.mac_address),
            "remote_id": str(ue.imsi),
            "expired": 0 if ue.ipv4 else 1,
            "api_key": self.__api_key,
        }
        if ue.ipv4:
            data["ip_address"] = str(ue.ipv4)
        resp = None
        try:
            self.logger.info(
                f"WOULD BE SENDING!!!!!!\n\t\t<< url: {url} data: {data} >>>"
            )
            # resp = requests.get(url, verify=False, params=data)
        except:
            self.logger.error(f"Could not update UE IP address in Sonar: {ue}")
        return resp
