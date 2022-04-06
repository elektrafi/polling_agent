#!/usr/bin/env python3

from pprint import pformat as _pprint
import logging as _logging
import asyncio
from multiprocessing import Process as _Process
from threading import Event as _Event
from multiprocessing.managers import (
    SyncManager as _SyncManager,
)
from queue import Queue as _Queue
from typing import (
    Callable as _Callable,
    Any as _Any,
    Coroutine as _Coroutine,
    Iterable as _Iterable,
)
from typing_extensions import Self as _Self

from model.atoms import Item as _Item
from model.network import IPv4Address as _IPv4Address
import time as _time
from functools import partial as _partial
from pickle import Pickler


class Attachment:
    sonar_id: str | None
    sonar_item_id: str
    timestamp: float
    address: _IPv4Address

    def __init__(self, si, ts=_time.time()):
        self.sonar_item_id = si
        self.timestamp = ts
        self.sonar_id = None

    def set_address(self, ipv4: _IPv4Address):
        self.address = _IPv4Address(address=repr(ipv4), cidr_mask=ipv4._cidr_mask)

    def __str__(self) -> str:
        return f'(id: {self.sonar_id if self.sonar_id else "NOT IN SONAR YET"}) Item id: {self.sonar_item_id} IP: {self.address} Attached at {_time.strftime("%m/%d/%y %H:%M:%S",_time.localtime(self.timestamp))}'

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self) -> int:
        return (
            hash(self.sonar_id)
            if self.sonar_id
            else 0 + hash(self.sonar_item_id)
            if self.sonar_item_id
            else 0 + hash(self.address)
            if self.address
            else 0
        )

    @classmethod
    def item_to_attachment(cls, item: _Item) -> _Self:
        attach = cls.__new__(cls)
        if item.ipv4:
            attach.address = _IPv4Address(
                octets=item.ipv4.address, netmask=item.ipv4.netmask
            )
        if item.sonar_id:
            attach.sonar_item_id = item.sonar_id
        attach.sonar_id = None
        attach.timestamp = _time.time()
        return attach


class PullAllocator:
    _manager: _SyncManager
    _queue: _Queue
    _current: dict[str, Attachment]
    _event: _Event
    _create: _Callable[[Attachment], _Coroutine[_Any, _Any, Attachment]]
    _update: _Callable[[Attachment], _Coroutine[_Any, _Any, Attachment]]
    _delete: _Callable[[Attachment], _Coroutine[_Any, _Any, Attachment]]
    _get_assignments: _Callable[[], _Coroutine[_Any, _Any, _Iterable[Attachment]]]
    _get_addresses: _Callable[[], _Coroutine[_Any, _Any, _Iterable[_Item]]]
    _logger = _logging.getLogger(__name__)
    _inventory: list[_Item]
    _delay: float

    def __init__(
        self,
        manager: _SyncManager,
        get_assignments: _Callable[[], _Coroutine[_Any, _Any, _Iterable[Attachment]]],
        get_addresses: _Callable[[], _Coroutine[_Any, _Any, _Iterable[_Item]]],
        create: _Callable[[Attachment], _Coroutine[_Any, _Any, Attachment]],
        update: _Callable[[Attachment], _Coroutine[_Any, _Any, Attachment]],
        delete: _Callable[[Attachment], _Coroutine[_Any, _Any, Attachment]],
        event: _Event,
        base_list: list[_Item],
        delay: float,
    ):
        self._delay = delay
        self._get_addresses = get_addresses
        self._get_assignments = get_assignments
        self._manager = manager
        self._create = create
        self._update = update
        self._delete = delete
        self._inventory = base_list
        self._event = event

    def new_poll(self):
        self._logger.debug(f"inventory list:\n{_pprint(self._inventory)}")
        while not self._event.is_set():
            attachments = set(asyncio.run(self._get_assignments()))
            addresses = asyncio.run(self._get_addresses())
            self._logger.debug(f"Attachements from sonar:\n{_pprint(attachments)}")
            self._logger.debug(f"Addresses from raemis:\n{_pprint(addresses)}")
            can_delete = True
            for address in addresses:
                try:
                    self._logger.debug(
                        f"Finding inventory item with IMSI: {address.imsi}"
                    )
                    item = next(
                        x for x in self._inventory if str(x.imsi) == str(address.imsi)
                    )
                    item.ipv4 = address.ipv4
                except:
                    self._logger.exception(
                        f"Unable to find matching item by imsi ({address.imsi}) for IP address {address.ipv4}, skipping item"
                    )
                    can_delete = False
                    continue
                try:
                    attachment = next(
                        x for x in attachments if x.sonar_item_id == item.sonar_id
                    )
                except:
                    self._logger.debug(
                        f"No attachment for item: {item.sonar_id} found in sonar, checking IP addresses"
                    )
                    try:
                        attachment = next(
                            x for x in attachments if x.address == item.ipv4
                        )
                    except:
                        self._logger.debug(
                            f"No attachment for IP address {item.ipv4} found in sonar, creating new allocation record"
                        )
                        try:
                            attachment = asyncio.run(
                                self._create(Attachment.item_to_attachment(item))
                            )
                            self._logger.info(f"created attachment: {attachment}")
                            continue
                        except:
                            self._logger.exception(
                                f"Failed to create an IP attachment in Sonar for item: {item} at address {item.ipv4}; will try again on the next pass"
                            )
                            continue
                if (
                    attachment.sonar_id is None
                    or item.ipv4 is None
                    or item.sonar_id is None
                ):
                    self._logger.error(
                        f"No sonar_id for attachment: {attachment}; skipping"
                    )
                    try:
                        self._logger.debug(
                            f"deleting {attachment} from the set of current attachemnts"
                        )
                        attachments.remove(attachment)
                    except:
                        self._logger.exception(
                            f"Failed to delete the attachment from the set; have to skip deletes this time"
                        )
                        can_delete = False
                    continue
                if (
                    attachment.address == item.ipv4
                    and attachment.sonar_item_id == item.sonar_id
                ):
                    self._logger.info(
                        f"{attachment} already has the IP address {item.ipv4} and associated item {item.sonar_id}, no need to update"
                    )
                    try:
                        self._logger.debug(
                            f"deleting {attachment} from the set of current attachemnts"
                        )
                        attachments.remove(attachment)
                    except:
                        self._logger.exception(
                            f"Failed to delete the attachment from the set; have to skip deletes this time"
                        )
                        can_delete = False
                    continue
                else:
                    self._logger.info(
                        f"updating {attachment} with ip address {item.ipv4}"
                    )
                    attachment.set_address(item.ipv4)
                    self._logger.debug(f"updated IP address for {attachment}")
                    self._logger.info(
                        f"updating {attachment} with item id {item.sonar_id}"
                    )
                    attachment.sonar_item_id = item.sonar_id
                    self._logger.debug(f"updated item ID for {attachment}")
                    try:
                        self._logger.debug(
                            f"attempting to update attachment: {attachment}"
                        )
                        attachment = asyncio.run(self._update(attachment))
                        self._logger.info(f"updated attachment: {attachment}")
                    except:
                        self._logger.exception(
                            f"Failed to update attachment: {attachment}; will try again next time"
                        )
                        can_delete = False
                    try:
                        self._logger.debug(
                            f"deleting {attachment} from the set of current attachemnts"
                        )
                        attachments.remove(attachment)
                    except:
                        self._logger.exception(
                            f"Failed to delete the attachment from the set; have to skip deletes this time"
                        )
                        can_delete = False
            self._logger.debug(f"attachments after loop:\n{attachments}")
            if can_delete:
                for attachment in attachments:
                    self._logger.info(
                        f"Remaining attachment {attachment} needs to be deleted from Sonar"
                    )
                    try:
                        if attachment.sonar_id is not None:
                            asyncio.run(self._delete(attachment))
                            self._logger.debug(f"deleted {attachment}")
                        else:
                            self._logger.error(
                                f"No sonar id for attachment {attachment}"
                            )
                    except:
                        self._logger.exception(
                            f"Failed to delete attachment: {attachment}"
                        )
            _time.sleep(self._delay)

    def poll(self):

        self._current = {}
        self._logger.info("start poller")
        while not self._event.is_set():
            to_del = list()
            for k in self._current:
                if _time.time() - self._current[k].timestamp > 12 * 60:
                    asyncio.run(self._delete(self._current[k]))
                    to_del.append(k)
            for d in to_del:
                del self._current[d]
            try:
                attach = self._queue.get(block=True, timeout=15)
                if not hasattr(attach, "sonar_id") or attach.sonar_id is None:
                    try:
                        attach.sonar_id = self._current[attach.sonar_item_id].sonar_id
                    except KeyError:
                        attach.sonar_id = None
                if hasattr(attach, "address"):
                    if not repr(attach.address).startswith("10."):
                        continue
            except:
                continue
            if not isinstance(attach, Attachment):
                self._logger.error(f"{attach} is not an Attachment object")
            if attach.sonar_id is None:
                try:
                    attach = asyncio.run(self._create(attach))
                    tmp = Attachment(attach.sonar_item_id)
                    tmp.sonar_id = attach.sonar_id
                    tmp.set_address(
                        _IPv4Address(
                            address=repr(attach.address),
                            cidr_mask=attach.address._cidr_mask,
                        )
                    )
                    self._current[attach.sonar_item_id] = tmp
                    self._logger.info(f"created attachment {tmp}")
                except:
                    self._logger.exception(
                        f"error when attempting to create IP address allocation: {attach}"
                    )
            else:
                try:
                    if attach.sonar_item_id in self._current and hasattr(
                        attach, "address"
                    ):
                        if not isinstance(attach.address, _IPv4Address):
                            self._logger.error(
                                f"{attach} has a incorrect type of obect"
                            )
                            continue
                        if repr(attach.address) != repr(
                            self._current[attach.sonar_item_id].address
                        ):
                            attach = asyncio.run(self._update(attach))
                            self._current[attach.sonar_item_id].timestamp = _time.time()
                            self._logger.info(f"updated attachment {attach}")
                            self._current[attach.sonar_item_id] = attach
                        else:
                            self._current[attach.sonar_item_id].timestamp = _time.time()
                            self._logger.info(
                                f"{attach.sonar_item_id} has not changed addresses from {self._current[attach.sonar_item_id].address}"
                            )
                            continue
                    else:
                        self._current[attach.sonar_item_id] = attach
                        self._current[attach.sonar_item_id].timestamp = _time.time()
                        self._logger.info(f"adding {attach} to dict")
                        continue

                except:
                    self._logger.exception(
                        f"error when attempting to update IP address allocation: {attach}"
                    )
        with open("allocations.dat", "w") as fi:
            p = Pickler(fi.buffer)
            try:
                p.dump(self._current)
            except:
                self._logger.exception(f"failed to pickle the allocations")
        self._logger.info("stopping polling loop")


class Allocator(object):
    import logging as _logging

    pending_allocations: _Queue
    _logger = _logging.getLogger(__name__)
    _loop_process: _Process
    _stop_event: _Any
    _ue_callback: _Callable[[str], _Item | None]
    # _sonar: _Sonar
    _api_key: str
    _inst: _Self | None = None

    def __init__(self, ue_callback: _Callable[[str], _Item | None]):
        self._logger.info("creating IP address allocator thread")
        # self._sonar = _Sonar()
        # self._api_key = self._sonar._sonar_api_key
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
