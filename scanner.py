#!/usr/bin/env python3
from routeros_api import Api
from ue import UE
from raemis import Raemis


class Scanner:
    def __init__(self):
        self.raemis = Raemis()
        self.mt = Api("10.176.1.1")
        self.dhcp_list = list()  # self.update_dhcp_clients()
        self.raemis_list = list()
        self.snmp_list = None

    async def update_dhcp_clients(self):
        self.dhcp_list = [
            UE(dhcp["active-address"])
            for dhcp in self.mt.talk("/ip/dhcp-server/lease/print")
            if dhcp["status"] == "bound"
        ]

    def get_dhcp_clients(self):
        return self.dhcp_list

    async def update_raemis_clients(self):
        self.raemis_list = [
            UE(client["ip"]) async for client in await self.raemis.get_data_sessions()
        ]

    def get_raemis_clients(self):
        return self.raemis_list
