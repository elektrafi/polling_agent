#!/usr/bin/env python3
from routeros_api import Api
from pprint import pprint
from ue import UE
from raemis import Raemis
import asyncio
from sonar_graphql import SonarGraphQL
from concurrent.futures import ThreadPoolExecutor
from mac_address import MACAddress

_executor = ThreadPoolExecutor(10)
_snmpExec = ThreadPoolExecutor(10)


class Scanner:
    def __init__(self) -> None:
        self.raemis = Raemis()
        self.mt = Api("10.176.1.1")
        self.dhcp_list = list()  # self.update_dhcp_clients()
        self.raemis_list = list()
        self.snmp_list = None
        self.sonar = SonarGraphQL()

    def update_dhcp_clients(self) -> None:
        self.dhcp_list = [
            UE(dhcp["active-address"])
            for dhcp in self.mt.talk("/ip/dhcp-server/lease/print")
            if dhcp["status"] == "bound"
        ]

    def get_dhcp_clients(self) -> list[UE]:
        return self.dhcp_list

    def update_raemis_clients(self) -> None:
        self.raemis_list = [
            UE(client["ip"]) for client in self.raemis.get_data_sessions()
        ]

    async def scan_snmp_info(self) -> None:
        tasks = []
        print("SNMP update")
        for ue in self.raemis_list:
            tasks.append(
                asyncio.get_event_loop().run_in_executor(_snmpExec, ue.fetch_ue_info)
            )
        await asyncio.gather(*tasks)
        print("SNMP finished")

    async def get_sonar_mac_addresses(self) -> None:
        print("Getting sonar info")
        task = await asyncio.get_event_loop().run_in_executor(
            _executor, self.sonar.get_inventory_with_mac
        )
        print("Sonar finished")
        if not task:
            return None
        self.sonar_mac = task

    async def update_sonar(self) -> None:
        tasks = []
        for ue in self.raemis_list:
            tasks.append(asyncio.to_thread(ue.update_sonar))
        await asyncio.gather(*tasks)

    def get_raemis_clients(self) -> list[UE]:
        return self.raemis_list

    async def update_remote_parallel(self) -> None:
        tasks = [
            self.scan_snmp_info(),
            # self.get_sonar_mac_addresses(),
        ]
        await asyncio.gather(*tasks)

    def run_scan(self) -> None:
        try:
            self.update_raemis_clients()
            print("done with raemis")
            asyncio.get_event_loop().run_until_complete(self.update_remote_parallel())
            print("Updated INFO!")

            # sonarMacList = [
            #    MACAddress(entity["value"])
            #    for item in self.sonar_mac
            #    if "inventory_model_field_data" in item
            #    and "entity" in item["inventory_model_field_data"]
            #    for entity in item["inventory_model_field_data"]["entity"]
            #    if entity["inventory_model_field"]["name"].lower().contains("mac")
            # ]

            fromSelfWithoutMac = [ue for ue in self.raemis_list if not ue.mac_address()]
            # scraped = [ue for ue in self.raemis_list if hasattr(ue, "scraper")]
            # notInSonarButHaveMac = [
            #    ue for ue in self.raemis_list if ue.mac_address() not in sonarMacList
            # ]

            print(
                "==============================================================================================="
            )
            print(
                "==============================================================================================="
            )
            pprint(fromSelfWithoutMac)
            print(
                "==============================================================================================="
            )
            # pprint(notInSonarButHaveMac)
            pprint(scraped)

            # self.sonar.insert_inventory(self.raemis_list)
            # asyncio.run(self.update_sonar())
            print("Done again")
        finally:
            asyncio.get_event_loop().run_until_complete(
                asyncio.get_event_loop().shutdown_asyncgens()
            )
            asyncio.get_event_loop().close()
