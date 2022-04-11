#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.


from numbers import Integral
from collections.abc import Sequence, Collection
from typing import Any, Collection, Iterator
from model.network import IPv4Address
import logging
from model.atoms import Item


class AddressList:
    _name: str
    _address_list: set[Item]

    def __init__(self, name: str, address_list: Collection[Item] = set()):
        self._name = name
        self._address_list = set(address_list)

    @property
    def name(self) -> str:
        return self._name

    @property
    def address_list(self) -> set[Item]:
        return self._address_list

    def add(self, address: Item) -> None:
        self._address_list.add(address)

    def remove(self, address: Item) -> None:
        self._address_list.remove(address)

    def api_format(self) -> Iterator[Any]:
        raise NotImplementedError("this must be implemented by subclasses")

    def api_update(self) -> None:
        raise NotImplementedError("this must be implemented by subclasses")


class FirewallRule:
    _enabled: bool
    _name: str
    comment: str
    _address_list: AddressList

    def __init__(
        self, name: str, addresses: AddressList, enabled=True, comment: str = ""
    ) -> None:
        self._enabled = enabled
        self._name = name
        self.comment = comment
        self._address_list = addresses

    @property
    def enabled(self) -> bool:
        return self._enabled

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def toggle(self) -> None:
        self._enabled = not self._enabled

    @property
    def name(self) -> str:
        return self._name

    @property
    def address_list(self) -> AddressList:
        return self._address_list

    def api_format(self) -> Any:
        raise NotImplementedError("this must be implemented by subclasses")

    def api_update(self) -> None:
        raise NotImplementedError("this must be implemented by subclasses")

    def __hash__(self) -> int:
        return hash(self._name)


class Firewall:
    _rules: set[FirewallRule]

    def __init__(self, rules: Collection[FirewallRule] = set()) -> None:
        self._rules = set(rules)

    @property
    def rules(self) -> set[FirewallRule]:
        return self._rules

    def add_rule(self, rule: FirewallRule) -> None:
        self._rules.add(rule)

    def delete_rule(self, rule: FirewallRule) -> None:
        self._rules.remove(rule)

    def add_rules(self, rules: Collection[FirewallRule]) -> None:
        self._rules.update(rules)


class BaseRouter:
    _logger = logging.getLogger(__name__)
    _address: IPv4Address
    _default_port: int
    _port_locked: bool
    _port: int
    _firewall: Firewall

    @property
    def address(self) -> IPv4Address:
        return self._address

    @address.setter
    def address(self, __o: object) -> None:
        if isinstance(__o, IPv4Address):
            self._address = IPv4Address(octets=__o.address, cidr_mask=__o._cidr_mask)
        elif isinstance(__o, Sequence):
            if not all(map(lambda x: isinstance(x, Integral), __o)):
                self._logger.error(f"not all elements of {str(__o)} are integers")
                raise ValueError("Elements of the sequence must be integers")
            else:
                self._address = IPv4Address(octets=tuple(__o))
        elif isinstance(__o, str):
            self._address = IPv4Address(address=__o)
        elif isinstance(__o, bytes):
            self._address = IPv4Address(address=__o.decode())
        else:
            try:
                self._address = IPv4Address(address=str(__o))
            except:
                self._logger.exception(f"{__o} is not an IP address")
                raise ValueError("Not an IP address")

    @property
    def port(self) -> int:
        return self._port

    @port.setter
    def port(self, __o: object) -> None:
        if self._port_locked:
            self._logger.warn(
                f"cannot change port to {str(__o)}, port is locked to {self._port}"
            )
            return
        if isinstance(__o, Integral):
            if int(__o) <= 0 or int(__o) >= 65535:
                self._logger.error(f"{str(__o)} is not a valid port")
                raise ValueError("cannot convert port value to int")
            self._port = int(__o)
        else:
            self._logger.error(f"{str(__o)} is not a valid port")
            raise ValueError("cannot convert port value to int")

    @property
    def firewall(self) -> Firewall:
        return self._firewall

    def __init__(self, default_port=22, port_locked=False):
        self._default_port = default_port
        self._port_locked = port_locked
        self._port = default_port
        self._firewall = Firewall()
