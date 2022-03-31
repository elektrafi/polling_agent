#!/usr/bin/env python3
from urllib3 import disable_warnings as _disable_warnings
from model.atoms import Account as _Account, Item as _Item, from_sonar as _from_sonar
from gql.transport.requests import (
    log as _gql_log,
)
from gql.transport.aiohttp import AIOHTTPTransport as _AIOHTTPTransport
from typing import (
    Any as _Any,
    Callable as Callable,
    Iterable as _Iterable,
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


_disable_warnings()


class Sonar:
    _apiUrl: str
    _logger = _logging.getLogger(__name__)
    _sonar_api_key: str

    @classmethod
    async def execute(cls, func) -> _Iterable[_Item]:
        _logging.basicConfig(level=_logging.INFO)
        transport = _AIOHTTPTransport(
            url=cls._apiUrl,
            timeout=None,
            headers={
                "Authorization": f"Bearer {cls._sonar_api_key}",
                "Accept": "application/json",
            },
        )
        _gql_log.setLevel(_logging.WARNING)
        async with _Client(transport=transport) as client:
            return await func(client)

    @classmethod
    async def get_inventory_items(
        cls,
        client: _AsyncClientSession,
    ) -> _Iterable[_Item]:
        cls._logger.info("getting inventory")
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
            ret = await cls._execute_paged_query(client, query)
        except:
            cls._logger.exception(
                "recieved no data from sonar when attempting to get all inventory items",
                stack_info=True,
            )
            return list([])
        return list(_exec.map(_Item.from_sonar, ret, chunksize=50))

    @classmethod
    async def get_accounts(
        cls,
        client: _AsyncClientSession,
    ) -> _Iterable[_Account]:
        cls._logger.info("getting account user names and id")
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
            ret = await cls._execute_paged_query(client, query)
        except:
            cls._logger.exception(
                "recieved no data from sonar when attempting to get all accounts and addresses",
                stack_info=True,
            )
            return list([])
        return list(_exec.map(_Account.from_sonar, ret, chunksize=50))

    @classmethod
    async def get_all_clients_and_assigned_inventory(
        cls,
        client: _AsyncClientSession,
    ) -> _Iterable[_Item]:
        cls._logger.info("getting account, addresses and inventory")
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
            d = await cls._execute_paged_query(client, query)
        except:
            cls._logger.exception(
                f"getting sonar accounts with assigned inventory failed",
                stack_info=True,
            )
            return list([])
        return list(_exec.map(_from_sonar, d, chunksize=50))

    @classmethod
    async def assign_inventory_item(
        cls, client: _AsyncClientSession, item: _Item
    ) -> dict[str, _Any]:

        if (
            not item
            or not item.sonar_id
            or not item
            or not item.account
            or not item.account.address
            or not item.account.address.sonar_id
        ):
            cls._logger.exception(
                "account, address or inventory item is null or does not have a linked sonar id",
                stack_info=True,
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
        cls._logger.info(f"assigning inventory item {item} to {item.account}")
        try:
            ret = await cls._execute_update(client, query, vs)
        except:
            cls._logger.exception(
                f"failed to assign {item} to {item.account}", stack_info=True
            )
            return dict()
        return ret

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
                f"error running update query for {name}", stack_info=True
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
if __name__ == "__main__":
    from pprint import pprint
    import asyncio

    pprint(asyncio.run(Sonar.execute(Sonar.get_accounts)))

_exec = _PPE()
