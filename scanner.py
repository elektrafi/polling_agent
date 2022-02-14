#!/usr/bin/env python3
import contextvars
from routeros_api import Api
from ue import UE
from raemis import Raemis
import asyncio


class Scanner:
    def __init__(self) -> None:
        self.raemis = Raemis()
        self.mt = Api("10.176.1.1")
        self.dhcp_list = list()  # self.update_dhcp_clients()
        self.raemis_list = list()
        self.snmp_list = None

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
        for ue in self.raemis_list:
            tasks.append(asyncio.to_thread(ue.fetch_has_snmp))
        await asyncio.gather(*tasks)
        tasks.clear()
        for ue in self.raemis_list:
            if ue.has_snmp():
                tasks.append(asyncio.to_thread(ue.fetch_hw_info))
        await asyncio.gather(*tasks)

    async def update_sonar(self) -> None:
        tasks = []
        for ue in self.raemis_list:
            tasks.append(asyncio.to_thread(ue.update_sonar))
        await asyncio.gather(*tasks)

    def get_raemis_clients(self) -> list[UE]:
        return self.raemis_list

    def run_scan(self) -> None:
        self.update_raemis_clients()
        print("done with raemis")
        asyncio.run(self.scan_snmp_info())
        print("Done with MAC addresses")
        # asyncio.run(self.update_sonar())
        print("Done again")
