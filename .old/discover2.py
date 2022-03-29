#!/usr/bin/env python3

import re
import logging
from concurrent.futures import Future
from .pipeline import Pipeline
from .sonar.api_connection import Sonar
from .genie_acs.api_connection import GenieACS
from .raemis.api_connection import Raemis
from .web_scraper.baicells import Baicells
from .raemis.event_listener import Listener
from .sonar.ip_allocation import Allocator
from .model.ue import UE, UEModel, UEManufacturer
from .model.mac_address import MACAddress
from .model.ip_address import IPv4Address
from .snmp import SNMP


class PollingAgent:
    logger = logging.getLogger(__name__)
    raemis: Raemis
    genis: GenieACS
    sonar: Sonar
    allocator: Allocator
    listener: Listener
    ue: list[UE]
    pipeline: Pipeline = Pipeline()

    def __init__(self):
        self.logger.info("starting polling agent")
        self.raemis = Raemis()
        self.genie = GenieACS()
        self.sonar = Sonar()
        self.listener = Listener()
        self.allocator = Allocator(self.__get_ue_by_imsi)
        self.allocator.start_loop()
        self.__startup()

    def __startup(self):
        def assign_ue(u: Future[list[UE]]):
            while not u.done():
                pass
            if u.exception():
                self.logger.error(
                    f"getting the inventory/accounts from sonar failed with: {u.exception()}"
                )
                return
            ue = u.result()
            if ue is None:
                self.logger.error("No acccounts or inventory came back from sonar")
                return
            self.ue = ue

        f = self.pipeline.start_fn(self.raemis.get_subscribers)
        f.add_done_callback(assign_ue)
        f = self.pipeline.start_fn_after_future(f, self.__get_ip_from_raemis)
        f = self.pipeline.start_fn_after_future(
            f, self.listener.start_event_receiver_server
        )
        f = self.pipeline.start_fn_after_future(f, self.__run_snmp_info)
        f = self.pipeline.start_fn_after_future(f, self.__baicells_web_scrapes)
        f = self.pipeline.start_fn_after_future(f, self.__get_sonar_data)
        self.pipeline.start_fn_after_future(
            f, lambda: self.logger.info("finished initializing")
        )

    def __get_sonar_data(self):
        data = self.sonar.get_all_clients_and_assigned_inventory()
        if data is None:
            self.logger.error("got empty result from sonar for accounts/inventory")
            return
        self.logger.info("assigning sonar info")

        def fn(datum: dict):
            client = datum["name"] if "name" in datum else ""
            self.logger.info(f"assigning sonar info for {client}")
            mac = None
            has_items = False
            has_address = False
            if (
                datum["addresses"]
                and datum["addresses"]["entities"]
                and datum["addresses"]["entities"][0]["inventory_items"]["entities"]
            ):
                has_address = True
                items = datum["addresses"]["entities"][0]["inventory_items"]["entities"]
                for item in items:
                    has_items = True
                    if (
                        item["inventory_model_field_data"]
                        and item["inventory_model_field_data"]["entities"]
                    ):
                        for field in item["inventory_model_field_data"]["entities"]:
                            name = ""
                            if (
                                field["inventory_model_field"]
                                and field["inventory_model_field"]["name"]
                            ):
                                name = (
                                    field["inventory_model_field"]["name"]
                                    .strip()
                                    .lower()
                                )
                            if not name:
                                self.logger.error(
                                    f'inventory field data has no name for data {field["value"] if "value" in field else "N/A"}'
                                )
                                continue
                            if "mac" in name:
                                mac = field["value"]
            if not mac:
                if not has_address:
                    self.logger.error(
                        f"sonar account for client has no servicable address: {client}"
                    )
                if has_items:
                    self.logger.error("inventory item has no mac address")
                else:
                    self.logger.error(
                        f'sonar account with no linked UE: (account id: {datum["id"] if "id" in datum else "ERR"}): {client}'
                    )
            ues = list(
                filter(
                    lambda x: x
                    and x.mac_address
                    and isinstance(mac, str)
                    and str(x.mac_address).strip().upper() == mac.strip().upper(),
                    self.ue,
                )
            )
            ue = None
            if not ues:
                self.logger.warn(f"no UE with mac {mac}, trying by name")
                if client:
                    ues = list(
                        filter(
                            lambda x: x
                            and x.client
                            and x.client.name
                            and all(
                                map(
                                    lambda y: y in client or "&" in y or " and " in y,
                                    x.client.name.split(" "),
                                )
                            ),
                            self.ue,
                        )
                    )
                    if ues:
                        ue = ues[0]
                        self.logger.info(
                            f"found match for {client} updating with sonar info"
                        )
                    else:
                        self.logger.warn(f"still no match for {client}")
                        return
                else:
                    self.logger.warn(f"still no match for {client}")
                    return
            elif len(ues) > 1:
                self.logger.warn(f"found multiple UE with MAC address {mac}: {ues}")
                self.logger.warn(f"using firrst UE: {ues[0]}")
            else:
                ue = ues[0]
                self.logger.info(f"found match for {mac} updating with sonar info")
            if ue:
                from_sonar(datum, ue)
                self.logger.debug(f"updated UE:\n{ue}")

        try:
            return list(self.pipeline.map(lambda x: fn(x), data))
        except:
            self.logger.exception("error in map function", stack_info=True)

    def __run_snmp_info(self):
        def f(ue: UE) -> None:
            if not ue._snmp:
                if ue.ipv4:
                    ue._snmp = SNMP(str(ue.ipv4))
                else:
                    return
            ue.info = ue._snmp.get_device_info()
            self.__snmp_guess_from_info(ue)
            match ue.model:
                case (UEModel.BEC6500 | UEModel.BEC6900 | UEModel.BEC7000):
                    ue.mac_address = ue._snmp.get_bec_mac_address()
                case UEModel.T12000:
                    ue.mac_address = ue._snmp.get_telrad_12000_mac_address()
                case UEModel.T12300:
                    ue.mac_address = ue._snmp.get_telrad_12300_mac_address()
            if ue.mac_address:
                self.logger.info(
                    f"found MAC address {str(ue.mac_address)} for UE with IMEI: {ue.imei}"
                )

        l = list()
        try:
            l = list(self.pipeline.map(lambda x: f(x), self.ue))
        except:
            self.logger.exception("error in map function", stack_info=True)
        self.logger.info(
            f"found {len([x for x in self.ue if x.mac_address])} UE mac addresses"
        )
        return l

    def __snmp_guess_from_info(self, u: UE) -> None:
        if u.info:
            i = u.info.lower()
            if u._snmp and u._snmp.try_check_telrad_12000():
                u.model = UEModel.T12000
                u.manufacturer = UEManufacturer.TELRAD
            elif "tel" in i or "gdm" in i:
                u.model = UEModel.T12300
                u.manufacturer = UEManufacturer.TELRAD
            elif "bec" in i or "ridgewave" in i:
                u.manufacturer = UEManufacturer.BEC
                u.model = UEModel.BEC6500
                if "7000" in i:
                    u.model = UEModel.BEC7000
                if "6900" in i:
                    u.model = UEModel.BEC6900
            elif "wap" in i or "generic" in i or "eftrt" in i:
                u.model = UEModel.WAC104
                u.manufacturer = UEManufacturer.NETGEAR
            elif "od06" in i or "baic" in i:
                u.model = UEModel.OD06
                u.manufacturer = UEManufacturer.BAICELLS

    def __baicells_web_scrapes(self) -> list[UE]:
        def fn(u: UE) -> UE:
            self.logger.debug(f"scraping: {u}")
            if not u.ipv4:
                return u
            try:
                b = Baicells(str(u.ipv4))
                mac = b.get_mac_address()
            except:
                self.logger.error(
                    f"could not get mac address from baicells {u.imei} {str(u.mac_address)} {str(u.ipv4)}"
                )
                return u
            u.mac_address = MACAddress(mac)
            self.logger.info(f"Baicells mac address {mac} assigned to {u.imei}")
            return u

        u = list(
            filter(
                lambda x: x
                and x.manufacturer == UEManufacturer.BAICELLS
                and x.ipv4
                and not x.mac_address,
                self.ue,
            )
        )

        self.logger.info("web scraping baicells")
        try:
            return list(self.pipeline.map(lambda x: fn(x), u))
        except:
            self.logger.exception("error in map function", stack_info=True)
            return list()

    def __get_ip_from_raemis(self):
        self.logger.info("getting ips from raemis")
        data = self.raemis.get_data_sessions()
        if data is None:
            return

        def f(ue: UE):
            if data is None:
                return
            try:
                d = next(
                    x
                    for x in data
                    if "imsi" in x
                    and hasattr(ue, "imsi")
                    and ue.imsi
                    and x["imsi"] == ue.imsi
                )
            except:
                self.logger.error(f"could not find a current IP address for {ue.imsi}")
                return
            if d is None:
                self.logger.warn(
                    f"unable to find data connection in Raemis for IMSI: {ue.imsi}"
                )
                return
            if "ip" in d and isinstance(d["ip"], str) and "." in d["ip"]:
                self.logger.info(f'assigning IP address {d["ip"]} to IMSI: {ue.imsi}')
                ue.set_host(IPv4Address(address=d["ip"]))
            ue.apn = d["apn"] if "apn" in d else None
            name = self.__guess_client_name(ue)
            manufacturer = self.__guess_ue_manufacturer(ue)
            model = self.__guess_ue_model(ue)
            ue.client.name = name
            ue.manufacturer = manufacturer
            ue.model = model
            self.logger.info(
                f"for UE IMEI: {ue.imei} found name: {name}, manufacturer: {str(manufacturer.value)}, model: {str(model.value)}"
            )

        try:
            return list(self.pipeline.map(f, self.ue))
        except:
            self.logger.exception("error in map function", stack_info=True)

    def __get_ue_by_imsi(self, imsi: str) -> UE | None:
        if not imsi:
            return None
        try:
            return next(
                filter(
                    lambda x: x and x.imsi and x.imsi.strip() == imsi.strip(), self.ue
                )
            )
        except:
            self.logger.error(f"could not fine UE with imsi {imsi}")
            return None

    def __guess_ue_model(self, d: UE) -> UEModel:
        if d.client.name is None:
            return UEModel.UNKNOWN
        part = re.split("""\s*_\s*""", d.client.name)[-1]
        if "bec" in part.lower() or part.lower().startswith("be"):
            if "6900" in part:
                return UEModel.BEC6900
            if "6500" in part:
                return UEModel.BEC6500
            if "7000" in part:
                return UEModel.BEC7000
        if "telr" in part.lower():
            if "1230" in part:
                return UEModel.T12300
            else:
                return UEModel.T12000
        if (
            "06" in part
            or "d6" in part.lower()
            or part.lower().startswith("o")
            or part.lower().startswith("b")
        ):
            return UEModel.OD06
        if "12300" in part:
            return UEModel.T12300
        if "6900" in part:
            return UEModel.BEC6900
        if "6500" in part:
            return UEModel.BEC6500
        if "7000" in part:
            return UEModel.BEC7000
        if "1200" in part:
            return UEModel.T12000

        return UEModel.UNKNOWN

    def __guess_ue_manufacturer(self, d: UE) -> UEManufacturer:
        if d.client.name is None:
            return UEManufacturer.UNKNOWN
        part = re.split("""\s*_\s*""", d.client.name)[-1]
        if "telrad" in part.lower() or part.lower().startswith("t"):
            return UEManufacturer.TELRAD
        if "bec" in part.lower() or part.lower().startswith("be"):
            return UEManufacturer.BEC
        if (
            "od" in part.lower()
            or part.lower().startswith("o")
            or part.lower().startswith("b")
        ):
            return UEManufacturer.BAICELLS
        return UEManufacturer.UNKNOWN

    def __guess_client_name(self, u: UE) -> str:
        if u.client is None or not u.client.name:
            return ""
        name = u.client.name
        if name.startswith("!"):
            return name
        if len(name.split("_")) >= 3:
            part = name.split("_")[0].strip()
            if (
                len(part.split(", ")) == 2
                or len(part.split(" ")) == 2
                or len(part.split(",")) == 2
            ):
                names = part.split(", ")
                if len(names) != 2:
                    names = part.split(" ")
                if len(names) != 2:
                    names = part.split(",")
                if len(names) == 2:
                    return f"{names[1].strip().lower().capitalize()} {names[0].strip().lower().capitalize()}"
            ret = ""
            for na in part.split(" "):
                if na.strip():
                    ret += (
                        "& "
                        if na.strip().lower() == "and"
                        else f"{na.strip().lower()} "
                    )
            ret = ret.strip()
            return ret.lower().title()
        try:
            n = name.lower().strip().index("setx")
        except:
            if name.isdigit():
                return ""
            ret = ""
            for na in name.split(" "):
                if na.strip():
                    ret += "& " if na.strip() == "and" else f"{na.strip().lower()} "
            ret = ret.strip()
            return ret.lower().title()
        tmp = name[:n]
        ret = ""
        for na in tmp.split(" "):
            if na.strip():
                ret += "& " if na.strip() == "and" else f"{na.strip().lower()} "
        ret = ret.strip()
        if name.isdigit():
            return ""
        return ret.lower().title()
