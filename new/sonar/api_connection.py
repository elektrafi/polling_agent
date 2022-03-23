#!/usr/bin/env python3

from typing_extensions import Self


from gql.transport.requests import RequestsHTTPTransport
from typing import Any

from gql import Client, gql
import re
from json import JSONDecoder
import logging

from graphql.execution.execute import ExecutionResult
from ..model.ue import UE

AccountType = type(dict[str, str | dict[str, list[dict[str, str]]]])
InventoryType = type(
    dict[
        str,
        str | dict[str, str | list[dict[str, str | dict[str, str]]]],
    ]
)


class Sonar:
    apiUrl: str
    client: Client
    logger = logging.getLogger(__name__)
    inst: Self | None = None
    sonar_api_key: str

    def __new__(cls: type[Self], *args, **kwargs) -> Self:
        if not cls.inst:
            cls.inst = object.__new__(cls, *args, **kwargs)
        return cls.inst

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

    def get_inventory_items(
        self,
    ) -> list[InventoryType] | None:
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
                      id,
                      name
                    }
                  },
                }
              }"""
        return self.__execute_paged_query(query)

    def get_account_id_and_name(
        self,
    ) -> list[AccountType] | None:
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
                    addresses(search:{boolean_fields:{attribute:"serviceable" search_value:true}}){
                      entities{
                        id,
                        line1,
                        line2,
                        city,
                        zip,
                        inventory_items{
                          entities{
                            id,
                          },
                        },
                      },
                    },
                  },
                }
              }"""
        return self.__execute_paged_query(query)

    def assign_inventory_item(self, ue: UE) -> dict[str, Any]:
        if (
            not ue
            or not ue.sonar_id
            or ue.client is None
            or ue.client.address is None
            or not ue.client.address.sonar_id
        ):
            self.logger.error(
                "UE is null or has no sonar_id; or, UE does not have an address with a sonar_id"
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
                "inventoryitemable_id": ue.client.address.sonar_id,
            },
            "id": ue.sonar_id,
        }
        self.logger.info(
            f"assigning inventory item {ue.sonar_id} to {ue.client.name} (id: {ue.client.sonar_id}) at (id: {ue.client.address.sonar_id}) {ue.client.address.line1}, {ue.client.address.city}, {ue.client.address.zip_code}"
        )
        return self.__execute_update(query, vs)

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
    ) -> None | list[Any]:
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
