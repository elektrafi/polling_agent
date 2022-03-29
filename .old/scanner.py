#!/usr/bin/env python3
from re import fullmatch
from bec_web_scrape import BECWebEmulator
from baicells import Baicells
from routeros_api import Api
from pprint import pprint
from ue import UE
from raemis import Raemis
import asyncio
from asyncio import Future
from sonar_graphql import SonarGraphQL
from concurrent.futures import ThreadPoolExecutor
from mac_address import MACAddress

_executor = ThreadPoolExecutor(10)
_snmpExec = ThreadPoolExecutor(100)
_settingsExec = ThreadPoolExecutor(100)


class Scanner:
    def __init__(self) -> None:
        self.raemis = Raemis()
        self.mt = Api("10.176.1.1")
        self.dhcp_list = list()
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

    async def update_sonar(self, l: list[UE]) -> None:
        await self.sonar.insert_inventory(l)

    def update_bec_settings(self, b: UE) -> None:
        try:
            bec = BECWebEmulator(b.hostname)
            bec.updateCWMPDefault()
            bec.disableFirewall()
            bec.updateSNMPDefault()
        except:
            print(f"Exception on {b.hostname}")

    async def update_bec_settings_list(self, l: list[UE]):
        print("BEC Settings starting")
        tasks = []
        for ue in l:
            tasks.append(
                asyncio.get_event_loop().run_in_executor(
                    _settingsExec, self.update_bec_settings, ue
                )
            )
        await asyncio.gather(*tasks)

        print("BEC Settings finished")

    def update_baicells_settings(self, b: UE) -> None:
        try:
            baicells = Baicells(b.hostname)
            baicells.update_firewall_settings()
            baicells.update_tr069_settings()
            baicells.update_upnp_settings()
        except:
            print(f"Exception on device {b.hostname}")

    async def update_baicells_settings_list(self, l: list[UE]):
        print("Baicells settings starting")
        tasks = []
        for ue in l:
            tasks.append(
                asyncio.get_event_loop().run_in_executor(
                    _settingsExec, self.update_baicells_settings, ue
                )
            )
        await asyncio.gather(*tasks)
        print("Baicells settings finished")

    async def update_settings(self, bec: list[UE], bai: list[UE]):
        tasks = [self.update_baicells_settings_list(bai)]
        tasks.append(self.update_bec_settings_list(bec))
        await asyncio.gather(*tasks)

    def get_raemis_clients(self) -> list[UE]:
        return self.raemis_list

    async def update_remote_parallel(self, runSonar: bool = True) -> None:
        tasks = [
            self.scan_snmp_info(),
        ]
        if runSonar:
            tasks.append(self.get_sonar_mac_addresses())

        await asyncio.gather(*tasks)

    def run_scan(self) -> None:
        updateSonar = False
        updateSettings = True
        try:
            self.update_raemis_clients()
            print("done with raemis")
            asyncio.get_event_loop().run_until_complete(
                self.update_remote_parallel(updateSonar)
            )
            print("Updated INFO!")

            fromSelfWithoutMac = [ue for ue in self.raemis_list if not ue.mac_address()]
            allWithMac = [ue for ue in self.raemis_list if ue.mac_address()]
            telrad = [
                ue
                for ue in self.raemis_list
                if (
                    str(ue.mac_address()).startswith("80")
                    or str(ue.mac_address()).startswith("34")
                )
            ]
            bec = [
                ue
                for ue in self.raemis_list
                if ue.ue_info
                and ("bec" in ue.ue_info.lower() or "ridgewave" in ue.ue_info.lower())
                and ue.mac_address()
            ]

            od06 = [
                od
                for od in allWithMac
                if od.ue_info
                and ("od06" in od.ue_info.lower() or "bai" in od.ue_info.lower())
            ]
            wac = [
                wac
                for wac in allWithMac
                if wac.ue_info and "wap" in wac.ue_info.lower()
            ]

            if updateSonar:
                sonarMacList = [
                    MACAddress(entity["value"])
                    for item in self.sonar_mac
                    if "inventory_model_field_data" in item
                    for entity in item["inventory_model_field_data"]["entities"]
                    if "mac" in entity["inventory_model_field"]["name"].lower()
                ]
                notInSonar = [
                    ue for ue in allWithMac if ue.mac_address() not in sonarMacList
                ]
                telNotSonar = [
                    tel
                    for tel in notInSonar
                    if str(tel.mac_address()).startswith("80")
                    or str(tel.mac_address()).startswith("34")
                ]
                becNotSonar = [
                    bec
                    for bec in notInSonar
                    if bec.ue_info
                    and (
                        "bec" in bec.ue_info.lower()
                        or "ridgewave" in bec.ue_info.lower()
                    )
                ]
                od06NotSonar = [
                    od for od in od06 if od.mac_address() not in sonarMacList
                ]
                wacNotSonar = [
                    wac
                    for wac in allWithMac
                    if wac.mac_address() not in sonarMacList
                    and wac.ue_info
                    and "wap" in wac.ue_info.lower()
                ]

            print(
                "==============================================================================================="
            )
            print(f"Total given from Raemis: {len(self.raemis_list)}")
            print(f"Still no MAC: {len(fromSelfWithoutMac)}")
            print(f"Telrad: {len(telrad)}")
            print(f"BEC: {len(bec)}")
            print(f"Baicells: {len(od06)}")
            print(f"Netgear: {len(wac)}")
            if updateSonar:
                print(f"Sonar has {len(sonarMacList)} devices")
                print(f"We have {len(notInSonar)} devices not in Sonar")
                print(f"    of those, {len(becNotSonar)} are BEC devices")
                print(f"    of those, {len(telNotSonar)} are Telrad devices")
                print(f"    of those, {len(od06NotSonar)} are Baicells devices")
                print(f"    of those, {len(wacNotSonar)} are Netgear devices")
            print(
                "==============================================================================================="
            )

            if updateSettings:
                asyncio.get_event_loop().run_until_complete(
                    self.update_settings(bec, od06)
                )

            if updateSonar:
                toSonar = becNotSonar.copy()
                toSonar.extend(telNotSonar)
                toSonar.extend(od06NotSonar)
                toSonar.extend(wacNotSonar)
                print(f"Total of {len(toSonar)} devices to be put in sonar")
                # asyncio.get_event_loop().run_until_complete(self.update_sonar(toSonar))
            print("Done again")
        finally:
            asyncio.get_event_loop().run_until_complete(
                asyncio.get_event_loop().shutdown_asyncgens()
            )
            asyncio.get_event_loop().close()
