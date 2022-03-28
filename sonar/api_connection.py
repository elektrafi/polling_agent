#!/usr/bin/env python3

from typing_extensions import Self

from ..model.atoms import Account, Item
from ..pipeline import Pipeline

from gql.transport.requests import RequestsHTTPTransport
from typing import Any, TypeVar, Callable

from gql import Client, gql
import re
from json import JSONDecoder
import logging

from graphql.execution.execute import ExecutionResult

AccountType = type(dict[str, str | dict[str, list[dict[str, str]]]])
InventoryType = type(
    dict[
        str,
        str | dict[str, str | list[dict[str, str | dict[str, str]]]],
    ]
)


T = TypeVar("T")
U = TypeVar("U")


class Sonar:
    apiUrl: str
    client: Client
    logger = logging.getLogger(__name__)
    _inst: Self | None = None
    sonar_api_key: str
    pipeline = Pipeline()

    def __new__(cls: type[Self], *args, **kwargs) -> Self:
        if not cls._inst:
            cls._inst = super(Sonar, cls).__new__(cls)
        return cls._inst

    def __init__(self, apiUrl: str = "https://elektrafi.sonar.software/api/graphql"):
        self.apiUrl = apiUrl
        with open("sonar_api.key") as key_file:
            self.sonar_api_key = JSONDecoder().decode(key_file.readline())[
                "sonar_api_key"
            ]
        transport = RequestsHTTPTransport(
            url=self.apiUrl,
            use_json=True,
            timeout=None,
            verify=False,
            retries=3,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=True)

    def __del__(self):
        if self.client.transport is not None:
            self.client.transport.close()

    def __process_list(self, l: list[T], proc: Callable[[T], U]) -> list[U]:
        def fn(d: T) -> U | None:
            try:
                return proc(d)
            except:
                self.logger.exception(
                    "error mapping raw data to objects", stack_info=True
                )
                return None

        return list([x for x in self.pipeline.map(fn, l) if x])

    def get_inventory_items(
        self,
    ) -> list[Item] | None:
        self.logger.info("getting inventory")
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
        ret = self.__execute_paged_query(query)
        if not ret:
            self.logger.error(
                "recieved no data from sonar when attempting to get all inventory items"
            )
            return None
        return self.__process_list(ret, Item.from_sonar)

    def get_accounts(
        self,
    ) -> list[Account] | None:
        self.logger.info("getting account user names and id")
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
        ret = self.__execute_paged_query(query)
        if not ret:
            self.logger.error(
                "recieved no data from sonar when attempting to get all accounts and addresses"
            )
            return None
        return self.__process_list(ret, Account.from_sonar)

    def get_all_clients_and_assigned_inventory(
        self,
    ) -> list[dict[str, Any]] | None:
        self.logger.info("getting account, addresses and inventory")
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
        d = self.__execute_paged_query(query)
        if d is None:
            return None
        return d

    def assign_inventory_item(self, account: Account, ue: Item) -> dict[str, Any]:
        if (
            not ue
            or not ue.sonar_id
            or not account
            or not account.address
            or not account.address.sonar_id
        ):
            self.logger.error(
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
                "inventoryitemable_id": account.address.sonar_id,
            },
            "id": ue.sonar_id,
        }
        self.logger.info(
            f"assigning inventory item {ue.sonar_id} to {account.name} (id: {account.sonar_id}) at (id: {account.address.sonar_id}) {account.address.line1}, {account.address.city}, {account.address.zip_code}"
        )
        ret = self.__execute_update(query, vs)
        if ret:
            ue

        return ret

    def __execute_update(self, query: str, vs: dict[str, Any]) -> dict[str, Any]:
        transport = RequestsHTTPTransport(
            url=self.apiUrl,
            use_json=True,
            timeout=None,
            verify=False,
            retries=3,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self.client.transport = transport
        if self.client.transport is None:
            self.logger.error("client has no transport object")
            raise ValueError
        try:
            self.client.transport.connect()
        except:
            self.logger.warn("transport already connected")
        name = query.split(" ")[1].split("(")[0]
        try:
            data = self.client.transport.execute(gql(query), variable_values=vs)
            self.logger.debug(f"ran update for {name} with values {vs}")
        except:
            self.logger.error(f"error running update query for {name}")
            raise ConnectionError
        if data is None or not isinstance(data, ExecutionResult):
            self.logger.error(f"incorrect or no data returned from sonar for {name}")
            raise ConnectionError
        if data.errors:
            for error in data.errors:
                self.logger.error(
                    f"received graphql error from sonar ({name}): {error.message}"
                )
            raise ConnectionError
        if data.data is None:
            self.logger.error(f"incorrect or no data returned from sonar for {name}")
            raise ConnectionError
        return data.data

    def __execute_paged_query(
        self, query: str, items_per_page: int = 100
    ) -> None | list[dict[str, Any]]:
        transport = RequestsHTTPTransport(
            url=self.apiUrl,
            use_json=True,
            timeout=None,
            verify=False,
            retries=3,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self.client.transport = transport
        page = {"page": {"page": 1, "records_per_page": items_per_page}}
        top = re.search(re.compile("""([a-zA-Z_]+)\(paginator..page."""), query)
        if top is None:
            self.logger.error("couldnt find the name of the paged item")
            raise ValueError
        top = top.groups()
        if top is None or len(top) == 0:
            self.logger.error("there were no groups for the paged item")
            raise ValueError
        paged = top[0]
        try:
            if self.client.transport is None:
                self.logger.error("transport is null")
                raise ValueError
            self.client.transport.connect()
        except:
            self.logger.warn("already connected")
        try:
            self.logger.info(f"getting page 1 of {paged}")
            if self.client.transport is None:
                raise ValueError
            data = self.client.transport.execute(gql(query), variable_values=page)
            if not isinstance(data, ExecutionResult):
                self.logger.error(
                    f"got the wrong type for a result, wanted ExecutionResult got {type(data)}"
                )
                raise ConnectionError
            if data.errors:
                for error in data.errors:
                    self.logger.error(
                        f"received graphql error from sonar: {error.message}"
                    )
                raise ConnectionError
            data = data.data
            if data is None:
                self.logger.error("no data returned from sonar")
                raise ConnectionError
            pageInfo = data[paged]["page_info"]
            numPages = pageInfo["total_pages"]
            currPage = pageInfo["page"]
            invItems = data[paged]["entities"]
            while currPage < numPages:
                page["page"]["page"] += 1
                try:
                    try:
                        self.logger.info(f"getting page {page} of {paged}")
                        data = self.client.transport.execute(
                            gql(query), variable_values=page
                        )
                        if not isinstance(data, ExecutionResult):
                            self.logger.error(
                                f"got the wrong type for a result, wanted ExecutionResult got {type(data)}"
                            )
                            continue
                        if data.errors:
                            for error in data.errors:
                                self.logger.error(
                                    f"received graphql error from sonar: {error.message}"
                                )
                            continue
                        data = data.data
                        if data is None:
                            self.logger.error("no data returned from sonar")
                            continue
                    except:
                        self.logger.error(
                            f'Failed while fetching paged data of page {page["page"]["[page]"]}'
                        )
                        continue
                    pageInfo = data[paged]["page_info"]
                    if numPages != pageInfo["total_pages"]:
                        self.logger.error("Different number of pages between requests")
                        raise ValueError
                    currPage = pageInfo["page"]
                    invItems.extend(data[paged]["entities"])
                except:
                    self.logger.error(
                        f"adding page {currPage} to aggregate result failed for {paged}"
                    )
                    continue
        except InterruptedError as ie:
            raise ie
        except Exception as e:
            raise e
        return invItems
