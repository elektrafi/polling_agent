#!/usr/bin/env python3

from functools import reduce as _reduce
from operator import iconcat as _iconcat
from typing_extensions import Self as _Self
from urllib3 import disable_warnings as _disable_warnings

_disable_warnings()

from ..model.atoms import Account as _Account, Item as _Item, from_sonar as _from_sonar
from ..pipeline import Pipeline as _Pipeline

from gql.transport.requests import (
    RequestsHTTPTransport as _RequestsHTTPTransport,
    log as _gql_log,
)
from typing import Any as _Any, TypeVar as _TypeVar, Callable as Callable

from gql import Client as _Client, gql as _gql
import re as _re
from json import JSONDecoder as _JSONDecoder
import logging as _logging

from graphql.execution.execute import ExecutionResult as _ExecutionResult


_T = _TypeVar("_T")
_U = _TypeVar("_U")


class Sonar:
    _apiUrl: str
    client: _Client
    _logger = _logging.getLogger(__name__)
    _inst: _Self | None = None
    _sonar_api_key: str
    _pipeline = _Pipeline()

    def __new__(cls: type[_Self], *args, **kwargs) -> _Self:
        if not cls._inst:
            cls._inst = super(Sonar, cls).__new__(cls)
        return cls._inst

    def __init__(self, apiUrl: str = "https://elektrafi.sonar.software/api/graphql"):
        self._apiUrl = apiUrl
        with open("sonar_api.key") as key_file:
            self._sonar_api_key = _JSONDecoder().decode(key_file.readline())[
                "sonar_api_key"
            ]
        transport = _RequestsHTTPTransport(
            url=self._apiUrl,
            use_json=True,
            timeout=None,
            verify=False,
            retries=3,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self._client = _Client(transport=transport, fetch_schema_from_transport=True)
        _gql_log.setLevel(_logging.WARNING)

    def __del__(self):
        if self._client.transport is not None:
            self._client.transport.close()

    def _process_list(
        self, l: list[_T], proc: Callable[[_T], _U | list[_U]]
    ) -> list[_U]:
        def fn(d: _T) -> _U | None:
            try:
                return proc(d)
            except:
                self._logger.exception(
                    "error mapping raw data to objects", stack_info=True
                )
                return None

        ret = list(x for x in self._pipeline.map(fn, l) if x)
        return _reduce(
            lambda x, y: _iconcat(x, y) if isinstance(y, list) else _iconcat(x, [y]),
            ret,
            [],
        )

    def get_inventory_items(
        self,
    ) -> list[_Item]:
        self._logger.info("getting inventory")
        query = """
              query ($page: Paginator!) {
                inventory_items(paginator:$page){
                  page_info {
                    page,
                    total_pages,
                  },
                  entities{
                    id
                    inventory_model_field_data {
                      entities {
                        inventory_model_field {
                          name
                        }
                        value
                      }
                    },
                    inventory_model {
                      name
                    }
                  },
                }
              }"""
        try:
            ret = self._execute_paged_query(query)
        except:
            self._logger.error(
                "recieved no data from sonar when attempting to get all inventory items"
            )
            return list()
        return self._process_list(ret, _Item.from_sonar)

    def get_accounts(
        self,
    ) -> list[_Account]:
        self._logger.info("getting account user names and id")
        query = """
              query ($page: Paginator!) {
                accounts(paginator:$page, account_status_id:1){
                  page_info {
                    page,
                    total_pages,
                  },
                  entities{
                    id,
                    name,
                    addresses(serviceable:true){
                      entities{
                        id,
                        line1,
                        line2,
                        city,
                        zip,
                      },
                    },
                  },
                }
              }"""
        try:
            ret = self._execute_paged_query(query)
        except:
            self._logger.error(
                "recieved no data from sonar when attempting to get all accounts and addresses"
            )
            return list()
        return self._process_list(ret, _Account.from_sonar)

    def get_all_clients_and_assigned_inventory(
        self,
    ) -> list[_Item]:
        self._logger.info("getting account, addresses and inventory")
        query = """
              query ($page:Paginator!) {
                accounts(paginator:$page, account_status_id:1) {
                  page_info {
                    page
                    total_pages
                    total_count
                  }
                  entities {
                    id
                    name
                    addresses(serviceable: true) {
                      entities {
                        id
                        line1
                        line1
                        city
                        zip
                        inventory_items {
                          entities {
                            id
                            inventory_model {
                              name
                            }
                            inventory_model_field_data {
                              entities {
                                inventory_model_field {
                                    name
                                }
                                value
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }"""
        try:
            d = self._execute_paged_query(query)
        except:
            self._logger.exception(
                f"getting sonar accounts with assigned inventory failed",
                stack_info=True,
            )
            return list()
        return self._process_list(d, _from_sonar)

    def assign_inventory_item(self, item: _Item) -> dict[str, _Any]:
        if (
            not item
            or not item.sonar_id
            or not item
            or not item.account
            or not item.account.address
            or not item.account.address.sonar_id
        ):
            self._logger.error(
                "account, address or inventory item is null or does not have a linked sonar id"
            )
            raise ValueError
        query = """
        mutation assignInventory($input: AssignInventoryItemsMutationInput, $id:[Int64Bit!]!){
          assignInventoryItems(input:$input, ids:$id){
            inventoryitemable_type,
            inventoryitemable_id,
          }
        }"""
        vs = {
            "input": {
                "inventoryitemable_type": "Address",
                "inventoryitemable_id": item.account.address.sonar_id,
            },
            "id": item.sonar_id,
        }
        self._logger.info(f"assigning inventory item {item} to {item.account}")
        try:
            ret = self._execute_update(query, vs)
        except:
            self._logger.exception(
                f"failed to assign {item} to {item.account}", stack_info=True
            )
            return dict()
        return ret

    def _execute_update(self, query: str, vs: dict[str, _Any]) -> dict[str, _Any]:
        transport = _RequestsHTTPTransport(
            url=self._apiUrl,
            use_json=True,
            timeout=None,
            verify=False,
            retries=3,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self._client.transport = transport
        if self._client.transport is None:
            self._logger.error("client has no transport object")
            raise ValueError
        try:
            self._client.transport.connect()
        except:
            self._logger.warn("transport already connected")
        name = query.split(" ")[1].split("(")[0]
        try:
            data = self._client.transport.execute(_gql(query), variable_values=vs)
            self._logger.debug(f"ran update for {name} with values {vs}")
        except:
            self._logger.error(f"error running update query for {name}")
            raise ConnectionError
        if data is None or not isinstance(data, _ExecutionResult):
            self._logger.error(f"incorrect or no data returned from sonar for {name}")
            raise ConnectionError
        if data.errors:
            for error in data.errors:
                self._logger.error(
                    f"received graphql error from sonar ({name}): {error.message}"
                )
            raise ConnectionError
        if data.data is None:
            self._logger.error(f"incorrect or no data returned from sonar for {name}")
            raise ConnectionError
        return data.data

    def _execute_paged_query(
        self, query: str, items_per_page: int = 100
    ) -> list[dict[str, _Any]]:
        transport = _RequestsHTTPTransport(
            url=self._apiUrl,
            use_json=True,
            timeout=None,
            verify=False,
            retries=3,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self._client.transport = transport
        page = {"page": {"page": 1, "records_per_page": items_per_page}}
        top = _re.search(_re.compile("""([a-zA-Z_]+)\(paginator..page."""), query)
        if top is None:
            self._logger.error("couldnt find the name of the paged item")
            raise ValueError
        top = top.groups()
        if top is None or len(top) == 0:
            self._logger.error("there were no groups for the paged item")
            raise ValueError
        paged = top[0]
        try:
            if self._client.transport is None:
                self._logger.error("transport is null")
                raise ValueError
            self._client.transport.connect()
        except:
            self._logger.warn("already connected")
        try:
            self._logger.debug(f"getting page 1 of {paged}")
            if self._client.transport is None:
                raise ValueError
            data = self._client.transport.execute(_gql(query), variable_values=page)
            if not isinstance(data, _ExecutionResult):
                self._logger.error(
                    f"got the wrong type for a result, wanted ExecutionResult got {type(data)}"
                )
                raise ConnectionError
            if data.errors:
                for error in data.errors:
                    self._logger.error(
                        f"received graphql error from sonar: {error.message}"
                    )
                raise ConnectionError
            data = data.data
            if data is None:
                self._logger.error("no data returned from sonar")
                raise ConnectionError
            pageInfo = data[paged]["page_info"]
            numPages = pageInfo["total_pages"]
            currPage = pageInfo["page"]
            invItems = data[paged]["entities"]
            while currPage < numPages:
                page["page"]["page"] += 1
                try:
                    try:
                        self._logger.info(f"getting page {page} of {paged}")
                        data = self._client.transport.execute(
                            _gql(query), variable_values=page
                        )
                        if not isinstance(data, _ExecutionResult):
                            self._logger.error(
                                f"got the wrong type for a result, wanted ExecutionResult got {type(data)}"
                            )
                            continue
                        if data.errors:
                            for error in data.errors:
                                self._logger.error(
                                    f"received graphql error from sonar: {error.message}"
                                )
                            continue
                        data = data.data
                        if data is None:
                            self._logger.error("no data returned from sonar")
                            continue
                    except:
                        self._logger.error(
                            f'Failed while fetching paged data of page {page["page"]["[page]"]}'
                        )
                        continue
                    pageInfo = data[paged]["page_info"]
                    if numPages != pageInfo["total_pages"]:
                        self._logger.error("Different number of pages between requests")
                        raise ValueError
                    currPage = pageInfo["page"]
                    invItems.extend(data[paged]["entities"])
                except:
                    self._logger.error(
                        f"adding page {currPage} to aggregate result failed for {paged}"
                    )
                    continue
        except InterruptedError as ie:
            raise ie
        except Exception as e:
            raise e
        return invItems
