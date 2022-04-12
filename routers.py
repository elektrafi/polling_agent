#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from main import Application
from model.atoms import Item
from routeros_api import RouterOsApiPool
from routeros_api.api import RouterOsApi
from routeros_api.resource import RouterOsResource
import logging


class MikroTikError(ConnectionError):
    pass


class MikroTikInsertionError(MikroTikError):
    pass


class MikroTikDeletionError(MikroTikError):
    pass


class MikroTikRouter:
    _logger = logging.getLogger(__name__)
    _api_client: RouterOsApi
    _address_lists: None | RouterOsResource
    _filter: None | RouterOsResource
    _api_pool: RouterOsApiPool

    def __init__(
        self,
        address=Application.config.mikrotik.host,
        port=Application.config.mikrotik.port,
        username=Application.config.mikrotik.username,
        password=Application.config.mikrotik.password,
    ):
        self._address_lists = None
        self._filter = None
        try:
            self._api_pool = RouterOsApiPool(
                host=address,
                username=username,
                password=password,
                port=port,
                use_ssl=True,
                ssl_verify=False,
                ssl_verify_hostname=False,
                plaintext_login=True,
            )
            self._api_pool.set_timeout(60)
            self._api_client = self._api_pool.get_api()
            self._logger.debug("MikroTik api client pool created")
        except:
            self._logger.exception("Failed to initilize MikroTik api pool")

    def __del__(self):
        if self._api_pool.connected:
            try:
                self._api_pool.disconnect()
            except:
                self._logger.exception("unable to disconnect mikrotik")

    def add_item_to_list(self, list_name: str, item: Item) -> None:
        if item.ipv4 is None:
            raise ValueError("IP address canot be null")
        if not list_name:
            raise ValueError("list name must have a value")
        item_id = str(item.sonar_id) if item.sonar_id else "N/A"
        account_id = (
            str(item.account.sonar_id)
            if item.account is not None and item.account.sonar_id
            else "N/A"
        )
        name = (
            str(item.account.name)
            if item.account is not None and item.account.name
            else "N/A"
        )
        try:
            self.address_lists.add(
                list=list_name,
                address=repr(item.ipv4),
                disabled="false",
                comment=f"item: {item_id}; account: {account_id}; name: {name}",
            )
        except:
            self._logger.exception(f"failed to remove {item} to liste {list_name}")
            raise MikroTikDeletionError(
                f"removal of address {repr(item.ipv4)} to address list {list_name} failed"
            )

    def remove_item_from_list(self, list_name: str, item: Item) -> None:
        if item.ipv4 is None:
            raise ValueError("IP address canot be null")
        if not list_name:
            raise ValueError("list name must have a value")
        try:
            self.address_lists.remove(list=list_name, address=repr(item.ipv4))
        except:
            self._logger.exception(f"failed to add {item} to liste {list_name}")
            raise MikroTikInsertionError(
                f"insertion of address {repr(item.ipv4)} to address list {list_name} failed"
            )

    @property
    def filter(self) -> RouterOsResource:
        if self._filter is None:
            try:
                self._filter = self._api_client.get_resource("/ip/firewall/filter")
            except:
                self._logger.exception("unable to get firewall filter rules")
                raise MikroTikError("cannot get firewall")
        return self._filter

    @property
    def address_lists(self) -> RouterOsResource:
        if self._address_lists is None:
            try:
                self._address_lists = self._api_client.get_resource(
                    "/ip/firewall/address-list"
                )
            except:
                self._logger.exception("unable to get firewall filter rules")
                raise MikroTikError("cannot get firewall")
        return self._address_lists