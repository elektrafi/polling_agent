from typing import Union
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from io import open
from json import JSONDecoder
from ue import UE

sonar_url = "https://elektrafi.sonar.software/api/graphql"


class SonarGraphQL:
    def __init__(self):
        with open("sonar_api.key") as key_file:
            self.sonar_api_key = JSONDecoder().decode(key_file.readline())[
                "sonar_api_key"
            ]
        transport = AIOHTTPTransport(
            url=sonar_url,
            ssl=True,
            ssl_close_timeout=50,
            headers={
                "Authorization": f"Bearer {self.sonar_api_key}",
                "Accept": "application/json",
            },
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=True)

    def get_inventory_with_mac(self) -> Union[None, dict]:
        query = gql(
            """
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
        )
        page = {"page": {"page": 1, "records_per_page": 100}}
        try:
            data = self.client.execute(query, variable_values=page)
            pageInfo = data["inventory_items"]["page_info"]
            numPages = pageInfo["total_pages"]
            currPage = pageInfo["page"]
            invItems = data["inventory_items"]["entities"]
            while currPage < numPages:
                page["page"]["page"] += 1
                try:
                    try:
                        data = self.client.execute(query, variable_values=page)
                    except:
                        raise InterruptedError("Failed while fetching paged data")
                    pageInfo = data["inventory_items"]["page_info"]
                    if numPages != pageInfo["total_pages"]:
                        raise ValueError("Different number of pages between requests")
                    currPage = pageInfo["page"]
                    invItems.extend(data["inventory_items"]["entities"])
                except:
                    raise ValueError(
                        "Unable to update paged data with newest page's information"
                    )
        except InterruptedError as ie:
            raise ie
        except Exception as e:
            raise e
        return invItems

    async def insert_inventory(self, ues: list[UE]) -> None:
        query = gql(
            """
            mutation InsertInventoryItem($input: CreateInventoryItemsMutationInput) {
                createInventoryItems(input: $input) {
                    inventory_model_id,
                     inventoryitemable_type,
                     inventory_model_field_data {
                         entities {
                             id,
                             value
                         }
                     }
                }
            }
            """
        )
        field_data_12000 = list()
        field_data_12300 = list()
        field_data_bec6900 = list()
        field_data_wac104 = list()
        field_data_bec6500 = list()
        field_data_od06 = list()
        for ue in ues:
            if ue.mac_address():
                if str(ue.mac_address()).startswith("80"):
                    field_data_12000.append(
                        [
                            {
                                "inventory_model_field_id": 38,
                                "value": str(ue.mac_address()),
                            },
                            {
                                "inventory_model_field_id": 39,
                                "value": str(ue.get_ue_info()),
                            },
                        ]
                    )
                elif str(ue.mac_address()).startswith("34"):
                    field_data_12300.append(
                        [
                            {
                                "inventory_model_field_id": 44,
                                "value": str(ue.mac_address()),
                            },
                            {
                                "inventory_model_field_id": 45,
                                "value": str(ue.get_ue_info()),
                            },
                        ]
                    )
                elif ue.get_ue_info() and "wap" in str(ue.get_ue_info()).lower():
                    field_data_wac104.append(
                        [
                            {
                                "inventory_model_field_id": 50,
                                "value": str(ue.mac_address()),
                            },
                            {
                                "inventory_model_field_id": 51,
                                "value": str(ue.get_ue_info()),
                            },
                        ]
                    )
                elif ue.get_ue_info() and "6900" in str(ue.get_ue_info()):
                    field_data_bec6900.append(
                        [
                            {
                                "inventory_model_field_id": 54,
                                "value": str(ue.mac_address()),
                            },
                            {
                                "inventory_model_field_id": 55,
                                "value": str(ue.get_ue_info()),
                            },
                        ]
                    )
                elif ue.get_ue_info() and ("6500" in str(ue.get_ue_info())):
                    field_data_bec6500.append(
                        [
                            {
                                "inventory_model_field_id": 60,
                                "value": str(ue.mac_address()),
                            },
                            {
                                "inventory_model_field_id": 61,
                                "value": str(ue.get_ue_info()),
                            },
                        ]
                    )
                elif ue.get_ue_info() and (
                    "od06" in str(ue.get_ue_info()).lower()
                    or "bai" in str(ue.get_ue_info()).lower()
                ):
                    field_data_od06.append(
                        [
                            {
                                "inventory_model_field_id": 66,
                                "value": str(ue.mac_address()),
                            },
                            {
                                "inventory_model_field_id": 71,
                                "value": str(ue.get_ue_info()),
                            },
                        ]
                    )

            self.data = [
                {
                    "input": {
                        "inventory_model_id": 13,
                        "inventoryitemable_type": "InventoryLocation",
                        "inventoryitemable_id": 1,
                        "items": [
                            {"individual_inventory_item_fields": fields}
                            for fields in field_data_12000
                        ],
                    }
                },
                {
                    "input": {
                        "inventory_model_id": 14,
                        "inventoryitemable_type": "InventoryLocation",
                        "inventoryitemable_id": 1,
                        "items": [
                            {"individual_inventory_item_fields": fields}
                            for fields in field_data_12300
                        ],
                    }
                },
                {
                    "input": {
                        "inventory_model_id": 15,
                        "inventoryitemable_type": "InventoryLocation",
                        "inventoryitemable_id": 1,
                        "items": [
                            {"individual_inventory_item_fields": field}
                            for field in field_data_bec6900
                        ],
                    },
                },
                {
                    "input": {
                        "inventory_model_id": 16,
                        "inventoryitemable_type": "InventoryLocation",
                        "inventoryitemable_id": 1,
                        "items": [
                            {"individual_inventory_item_fields": field}
                            for field in field_data_bec6500
                        ],
                    },
                },
                {
                    "input": {
                        "inventory_model_id": 1,
                        "inventoryitemable_type": "InventoryLocation",
                        "inventoryitemable_id": 1,
                        "items": [
                            {"individual_inventory_item_fields": field}
                            for field in field_data_wac104
                        ],
                    },
                },
                {
                    "input": {
                        "inventory_model_id": 2,
                        "inventoryitemable_type": "InventoryLocation",
                        "inventoryitemable_id": 1,
                        "items": [
                            {"individual_inventory_item_fields": field}
                            for field in field_data_od06
                        ],
                    },
                },
            ]
        try:
            print(
                "TOTAL ITEMS INSERTED: %d"
                % sum(
                    (
                        len(field_data_12300),
                        len(field_data_12000),
                        len(field_data_wac104),
                        len(field_data_bec6900),
                        len(field_data_bec6500),
                    )
                )
            )
            transport = AIOHTTPTransport(
                url=sonar_url,
                ssl=True,
                ssl_close_timeout=50,
                headers={
                    "Authorization": f"Bearer {self.sonar_api_key}",
                    "Accept": "application/json",
                },
            )
            self.client = Client(transport=transport, fetch_schema_from_transport=True)
        except:
            print("Failed to create client to transport Data!")
            return
        for d in self.data:
            try:
                result = await self.client.execute_async(query, variable_values=d)
                print(*[f"Res: {str(r)}\n" for r in result])
            except Exception as e:
                print(f"Oh no! FAILED\n{e.__repr__()}")
        return


if __name__ == "__main__":
    pass
    # print(SonarGraphQL().get_users())
