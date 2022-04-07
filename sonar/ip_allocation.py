#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.


import logging as _logging
from asyncio import run as _run
from threading import Event as _Event
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
        self._create = create
        self._update = update
        self._delete = delete
        self._inventory = base_list
        self._event = event

    def poll(self):
        self._logger.debug(f"inventory list:\n{self._inventory}")
        while not self._event.is_set():
            attachments = set(_run(self._get_assignments()))
            addresses = _run(self._get_addresses())
            self._logger.debug(f"Attachements from sonar:\n{attachments}")
            self._logger.debug(f"Addresses from raemis:\n{addresses}")
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
                            attachment = _run(
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
                        attachment = _run(self._update(attachment))
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
                            _run(self._delete(attachment))
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
