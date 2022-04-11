#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import asyncio
from asyncio.tasks import Task
from urllib3 import disable_warnings as _disable_warnings
from model.atoms import (
    Account as _Account,
    Item as _Item,
    Name,
    from_sonar as _from_sonar,
    Model as _Model,
)
from gql.transport.requests import (
    log as _gql_log,
)
from gql.transport.aiohttp import AIOHTTPTransport as _AIOHTTPTransport
import gql
import gql.transport.aiohttp
import gql.client
from typing import (
    Any as _Any,
    Callable as Callable,
    Iterable as _Iterable,
    Coroutine as _Coroutine,
    TypeVar as _TypeVar,
    Callable as _Callable,
)
from gql import gql as _gql
from gql.client import (
    AsyncClientSession as _AsyncClientSession,
    Client as _Client,
)
import re as _re
from json import JSONDecoder as _JSONDecoder
import logging as _logging
from concurrent.futures import ProcessPoolExecutor as _PPE
from asyncio import gather as _gather
import sonar.queries as _q
from sonar.ip_allocation import Attachment as _Attachment
from model.network import IPv4Address as _IPv4Address

_gql_log.setLevel(_logging.WARNING)

_disable_warnings()

from functools import partial as _partial

_T = _TypeVar("_T")


class Sonar:
    _apiUrl: str
    _logger = _logging.getLogger(__name__)
    _sonar_api_key: str

    @classmethod
    async def execute(
        cls,
        func: _Callable[..., _Coroutine[_Any, _Any, _T]],
        *args,
        **kwargs,
    ) -> _T:
        transport = _AIOHTTPTransport(
            url=cls._apiUrl,
            ssl_close_timeout=240,
            timeout=None,
            headers={
                "Authorization": f"Bearer {cls._sonar_api_key}",
                "Accept": "application/json",
            },
        )
        _gql_log.setLevel(_logging.WARNING)
        async with _Client(transport=transport, execute_timeout=240) as client:
            return await func(client, *args, **kwargs)

    @classmethod
    async def create_missing(cls, items: _Iterable[_Item]) -> _Iterable[_Item]:
        create_items: _Iterable[Task[_Item]] = list()
        for item in items:
            if not item.sonar_id or item.sonar_id is None:
                if (
                    item.mac_address is not None
                    and item.imei is not None
                    and item.imsi is not None
                ):
                    try:
                        create_items.append(
                            asyncio.create_task(cls.execute(cls.create_item, item))
                        )
                    except:
                        cls._logger.exception(f"failed creating {item}")
        try:
            return await _gather(*create_items)
        except:
            cls._logger.exception(f"failed creating items", stack_info=True)
            return list()

    @classmethod
    async def add_raemis_name_to_items(
        cls, items: _Iterable[_Item]
    ) -> _Iterable[_Item]:
        updated = list()
        for item in items:
            if (
                not item.sonar_id
                or item.model in [_Model.UNKNOWN, _Model.WAC104]
                or item.account is None
                or not item.account.name
                or item.account.sonar_id is not None
            ):
                continue
            try:
                updated.append(
                    asyncio.create_task(cls.execute(cls.add_raemis_name_to_notes, item))
                )
            except:
                cls._logger.exception(f"failed adding info to notes field for {item}")
        try:
            return await _gather(*updated)
        except:
            cls._logger.exception(f"failed updating notes for items")
            return list()

    @classmethod
    async def update_needed(cls, items: _Iterable[_Item]) -> _Iterable[_Item]:
        updated = list()
        for item in items:
            if (
                item.model == _Model.UNKNOWN
                or item.model == _Model.WAC104
                or item.sonar_id is None
                or not item.sonar_id
            ):
                continue
            try:
                updated.append(
                    asyncio.create_task(cls.execute(cls.update_item_fields, item))
                )
            except:
                cls._logger.exception(f"failed updaiting {item}")
        try:
            return await _gather(*updated)
        except:
            cls._logger.exception(f"failed updating items", stack_info=True)
            return list()

    @classmethod
    async def match_names_and_link(cls, items: _Iterable[_Item]):
        try:
            accounts = await asyncio.create_task(cls.execute(cls.get_accounts))
            tasks = list()
            for item in items:
                try:
                    if (
                        item.account is None
                        or item.sonar_id is None
                        or not item.account
                        or item.account.name is None
                        or not item.account.name
                        or item.account.sonar_id is not None
                        or item.linked_to_account
                    ):
                        continue
                    name = item.account.name.replace(" & ", "")
                    parts = _re.split(r"\s+", str(name))
                    for account in accounts:
                        if (
                            account.name is None
                            or account.sonar_id is None
                            or not account.name
                            or account.address is None
                            or not account.address.sonar_id
                        ):
                            continue
                        if all(map(lambda x: str(x) in str(account.name), parts)):
                            cls._logger.info(f"linking {item} to {account}")
                            item.account = account
                            try:
                                tasks.append(
                                    asyncio.create_task(
                                        cls.execute(cls.assign_inventory_item, item)
                                    )
                                )
                            except:
                                cls._logger.exception(
                                    f"failed linking {item} and {account}"
                                )
                            break
                except:
                    continue
            return await _gather(*tasks)
        except:
            cls._logger.exception("failed matching badly")

    @classmethod
    async def link_to_accounts(cls, items: _Iterable[_Item]) -> _Iterable[_Item]:
        linked = list()
        for item in items:
            if (
                item.sonar_id
                and item.account
                and item.account.sonar_id
                and item.account.address
                and item.account.address.sonar_id
                and not item.linked_to_account
            ):
                linked.append(
                    asyncio.create_task(cls.execute(cls.assign_inventory_item, item))
                )
        return await _gather(*linked)

    @classmethod
    async def get_ip_address_assignments(cls) -> _Iterable[_Attachment]:
        attachments = list()
        try:
            infos = await asyncio.create_task(
                cls.execute(cls._execute_paged_query, _q.current_ip_address_assignments)
            )
            for info in infos:
                try:
                    if (
                        "ipassignmentable_id" in info
                        and "subnet" in info
                        and "id" in info
                    ):
                        ret = _Attachment(info["ipassignmentable_id"])
                        ret.set_address(_IPv4Address(address=info["subnet"]))
                        ret.sonar_id = info["id"]
                        attachments.append(ret)
                        cls._logger.info(
                            f"got assignment (id {ret.sonar_id}) at {ret.address} for {ret.sonar_item_id}"
                        )
                except:
                    cls._logger.exception(f"failed to create attachemt for {info}")
                    continue
        except:
            cls._logger.exception(f"failed to get ip address attachments")
        return attachments

    @classmethod
    async def update_ip_assignment(cls, attach: _Attachment):
        data = {
            "id": attach.sonar_id,
            "input": {
                "subnet": repr(attach.address),
                "ipassignmentable_id": attach.sonar_item_id,
                "soft": True,
                "ipassignmentable_type": "InventoryItem",
                "reference": attach.sonar_item_id,
            },
        }
        try:
            ret = await asyncio.create_task(
                cls.execute(cls._execute_update, _q.update_ip_assignment, data)
            )
            back = ret["updateIpAssignment"]
            attach.sonar_id = back["id"]
            attach.set_address(_IPv4Address(address=back["subnet"]))
            cls._logger.info(
                f"updated ip assignment (id: {attach.sonar_id}) for item {attach.sonar_item_id} to address {attach.address}."
            )
        except:
            cls._logger.exception(
                f"failed to update {attach}",
                stacklevel=_logging.CRITICAL,
            )
        return attach

    @classmethod
    async def delete_ip_assignment(cls, attach: _Attachment) -> _Attachment:
        data = {"id": attach.sonar_id}
        try:
            _ = await asyncio.create_task(
                cls.execute(cls._execute_update, _q.delete_ip_assignment, data)
            )
            cls._logger.info(
                f"deleted ip assignment (id: {attach.sonar_id}) for item {attach.sonar_item_id}"
            )
        except:
            cls._logger.exception(
                f"failed to delete {attach}",
                stacklevel=_logging.CRITICAL,
            )
        return attach

    @classmethod
    async def create_ip_assignment(cls, attach: _Attachment):
        data = {
            "input": {
                "subnet": repr(attach.address),
                "soft": True,
                "ipassignmentable_id": attach.sonar_item_id,
                "ipassignmentable_type": "InventoryItem",
                "reference": attach.sonar_item_id,
            }
        }
        try:
            ret = await asyncio.create_task(
                cls.execute(cls._execute_update, _q.create_ip_assignment, data)
            )
            back = ret["createIpAssignment"]
            attach.sonar_id = back["id"]
            attach.set_address(_IPv4Address(address=back["subnet"]))
            cls._logger.info(
                f"(id: {attach.sonar_id}) created ip assignment to address {attach.address} for item {attach.sonar_item_id}."
            )
        except:
            cls._logger.exception(
                f"failed to create {attach}",
                stacklevel=_logging.CRITICAL,
            )
        return attach

    @classmethod
    async def get_inventory_items(
        cls,
        client: _AsyncClientSession,
    ) -> _Iterable[_Item]:
        cls._logger.info("getting inventory")
        try:
            ret = await cls._execute_paged_query(client, _q.get_inventory_items)
        except:
            cls._logger.exception(
                "recieved no data from sonar when attempting to get all inventory items",
                stack_info=True,
                stacklevel=_logging.CRITICAL,
            )
            return list([])
        return list(_exec.map(_Item.from_sonar, ret, chunksize=50))

    @classmethod
    async def get_accounts(
        cls,
        client: _AsyncClientSession,
    ) -> _Iterable[_Account]:
        cls._logger.info("getting account user names and id")
        try:
            ret = await cls._execute_paged_query(client, _q.get_accounts)
        except:
            cls._logger.exception(
                "recieved no data from sonar when attempting to get all accounts and addresses",
                stacklevel=_logging.CRITICAL,
            )
            return list([])
        return list(_exec.map(_Account.from_sonar, ret, chunksize=50))

    @classmethod
    async def get_all_clients_and_assigned_inventory(
        cls,
        client: _AsyncClientSession,
    ) -> _Iterable[_Item]:
        cls._logger.info("getting account, addresses and inventory")
        try:
            d = await cls._execute_paged_query(
                client, _q.get_accounts_and_assigned_inventory
            )
        except:
            cls._logger.exception(
                f"getting sonar accounts with assigned inventory failed",
                stack_info=True,
                stacklevel=_logging.CRITICAL,
            )
            return list([])
        return list(_exec.map(_from_sonar, d, chunksize=50))

    @classmethod
    async def update_billing_parameters(
        cls, client: _AsyncClientSession, account_id: str
    ):
        data = {
            "id": account_id,
            "input": {"grace_days": 25, "days_of_delinquency_for_status_switch": 0},
        }
        try:
            ret = await cls._execute_update(client, _q.update_billing_parameters, data)
            return ret
        except:
            cls._logger.exception(f"Failed to update account {account_id}")

    @classmethod
    async def assign_inventory_item(
        cls, client: _AsyncClientSession, item: _Item, loc_type: str = "Address"
    ) -> _Item:

        if (
            not item
            or not item.sonar_id
            or not item.account
            or not item.account.sonar_id
            or not item.account.address
            or not item.account.address.sonar_id
        ):
            cls._logger.critical(
                "account, address or inventory item is null or does not have a linked sonar id",
                stack_info=True,
            )
            raise ValueError
        vs = {
            "input": {
                "inventoryitemable_type": loc_type,
                "inventoryitemable_id": item.account.address.sonar_id,
            },
            "id": item.sonar_id,
        }
        cls._logger.info(f"assigning inventory item {item} to {item.account}")
        try:
            ret = await cls._execute_update(client, _q.assign_inventory, vs)
            cls._logger.info(f"assigned item to account: {ret}")
        except:
            cls._logger.exception(
                f"failed to assign {item} to {item.account}",
                stacklevel=_logging.CRITICAL,
            )
        return item

    @classmethod
    async def update_item_fields(
        cls, client: _AsyncClientSession, item: _Item
    ) -> _Item:
        if item.model in [_Model.UNKNOWN, _Model.WAC104] or item.sonar_id is None:
            return item
        data: dict[str, _Any] = {
            "id": item.sonar_id,
            "input": {
                "fields": [
                    {
                        "inventory_model_field_id": _q.inventory_field_ids[item.model][
                            field
                        ],
                        "value": str(getattr(item, field)),
                    }
                    for field in _q.inventory_field_ids[item.model]
                    if getattr(item, field) is not None and getattr(item, field)
                ]
            },
        }
        try:
            data = await cls._execute_update(client, _q.update_item_field, data)
            cls._logger.info(f"updated item: {data}")
        except:
            cls._logger.exception(
                f"error updating item: {item.sonar_id} -- IP/mac: {item.ipv4 if item.ipv4 else item.mac_address}/{item.mac_address} item: {item}",
                stacklevel=_logging.CRITICAL,
            )
        return item

    @classmethod
    async def add_raemis_name_to_notes(cls, client: _AsyncClientSession, item: _Item):
        if (
            item.model in [_Model.UNKNOWN, _Model.WAC104]
            or item.sonar_id is None
            or item.account is None
            or not item.account.name
            or item.account.sonar_id is not None
            or item.account.sonar_id
        ):
            return item
        data = {
            "id": item.sonar_id,
            "input": {
                "note": {"message": str(item.account.name), "priority": "NORMAL"}
            },
        }
        try:
            ret = await cls._execute_update(client, _q.update_inventory_item, data)
            cls._logger.info(f"added raemis info to item: {ret}")
        except:
            cls._logger.exception(
                f"error adding raemis info to item: {item} for {data}"
            )
        return item

    @classmethod
    async def create_item(cls, client: _AsyncClientSession, item: _Item) -> _Item:
        if (
            item.model != _Model.UNKNOWN
            and item.model != _Model.WAC104
            and not item.sonar_id
            and item.mac_address
            and item.imei is not None
        ):
            data = {
                "input": {
                    "inventory_model_id": _Model.item_to_sonar_id(item),
                    "inventoryitemable_type": "InventoryLocation",
                    "inventoryitemable_id": 2,
                    "items": [
                        {
                            "individual_inventory_item_fields": [
                                {
                                    "inventory_model_field_id": _q.inventory_field_ids[
                                        item.model
                                    ][field],
                                    "value": str(getattr(item, field)),
                                }
                                for field in _q.inventory_field_ids[item.model]
                                if getattr(item, field) is not None
                                and getattr(item, field)
                            ],
                        },
                    ],
                }
            }
            try:
                ids = await cls._execute_update(client, _q.create_item, data)
                item.sonar_id = ids["createInventoryItems"][0]["id"]
                cls._logger.info(f"created item: {ids}")
            except:
                cls._logger.exception(
                    f"error creating item: {item.sonar_id} -- IP/mac: {item.ipv4 if item.ipv4 else item.mac_address}/{item.mac_address} item: {item}",
                    stacklevel=_logging.CRITICAL,
                )
        return item

    @classmethod
    async def _execute_update(
        cls, client: _AsyncClientSession, query: str, vs: dict[str, _Any]
    ) -> dict[str, _Any]:
        name = query.split(" ")[1].split("(")[0]
        try:
            data = await client.execute(_gql(query), variable_values=vs)
            cls._logger.debug(f"ran update for {name} with values {vs}")
        except:
            cls._logger.exception(
                f"error running update query for {name} with values: {vs}",
            )
            raise ConnectionError
        if data is None or not isinstance(data, dict):
            cls._logger.error(f"incorrect or no data returned from sonar for {name}")
            raise ConnectionError
        return data

    @classmethod
    async def _execute_paged_query(
        cls, client: _AsyncClientSession, query: str, items_per_page: int = 100
    ) -> _Iterable[dict[str, _Any]]:
        page = {"page": {"page": 1, "records_per_page": items_per_page}}
        top = _re.search(_re.compile(r"""([a-zA-Z_]+)\(paginator..page."""), query)
        if top is None:
            cls._logger.error("couldnt find the name of the paged item")
            raise ValueError
        top = top.groups()
        if top is None or len(top) == 0:
            cls._logger.error("there were no groups for the paged item")
            raise ValueError
        paged = top[0]
        try:
            cls._logger.debug(f"getting page 1 of {paged}")
            data = await client.execute(_gql(query), variable_values=page)
            if not isinstance(data, dict):
                cls._logger.error(
                    f"got the wrong type for a result, wanted ExecutionResult got {type(data)}"
                )
                raise ConnectionError
            pageInfo = data[paged]["page_info"]
            numPages = pageInfo["total_pages"]
            currPage = pageInfo["page"]
            invItems = data[paged]["entities"]
            while currPage < numPages:
                page["page"]["page"] += 1
                try:
                    try:
                        cls._logger.info(f"getting page {page} of {paged}")
                        data = await client.execute(_gql(query), variable_values=page)
                        if not isinstance(data, dict):
                            cls._logger.error(
                                f"got the wrong type for a result, wanted ExecutionResult got {type(data)}"
                            )
                            continue
                    except:
                        cls._logger.exception(
                            f'Failed while fetching paged data of page {page["page"]["[page]"]}',
                            stack_info=True,
                        )
                        continue
                    pageInfo = data[paged]["page_info"]
                    if numPages != pageInfo["total_pages"]:
                        cls._logger.error("Different number of pages between requests")
                        raise ValueError
                    currPage = pageInfo["page"]
                    invItems.extend(data[paged]["entities"])
                except:
                    cls._logger.exception(
                        f"adding page {currPage} to aggregate result failed for {paged}",
                        stack_info=True,
                    )
                    continue
        except InterruptedError as ie:
            raise ie
        except Exception as e:
            raise e
        return invItems


apiUrl: str = "https://elektrafi.sonar.software/api/graphql"
Sonar._apiUrl = apiUrl
with open("sonar_api.key") as key_file:
    Sonar._sonar_api_key = _JSONDecoder().decode(key_file.readline())["sonar_api_key"]

_exec = _PPE()
