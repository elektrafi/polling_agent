#!/usr/bin/env python3
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    ParamSpec,
    TypeVar,
)

from new.web_scraper.bec import BECWebEmulator
from .model.mac_address import MACAddress
import re
from .model.ip_address import IPv4Address
from .raemis.api_connection import Raemis
from .genie_acs.api_connection import GenieACS
from .sonar.api_connection import Sonar, AccountType, InventoryType
from .model.ue import UE, UEManufacturer, UEModel, Address
from concurrent.futures import ThreadPoolExecutor, Future
from .web_scraper.baicells import Baicells
import logging

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", list[Future], Future)
FList = type(list[Future[Any]])
TPE = type(ThreadPoolExecutor)


class Pipeline:
    mainExec: ThreadPoolExecutor
    __executors: set[ThreadPoolExecutor]
    cursor: Future

    def __init__(self, pool_size: int = 175):
        self.mainExec = ThreadPoolExecutor(max_workers=pool_size)
        self.__executors = {self.mainExec}
        self.cursor = Future()

    def __del__(self):
        (x.shutdown(wait=True, cancel_futures=False) for x in self.__executors)

    def map(
        self,
        fn: Callable[P, T],
        iterable: Iterable[Any] | Any,
        timeout: float | None = None,
        chunksize: int = -1,
    ) -> Iterator[T]:
        return self.mainExec.map(fn, iterable, timeout=timeout, chunksize=chunksize)

    def start_fn_in_executor(
        self,
        e: TPE,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        self.__executors.add(e)
        self.cursor = e.submit(fn, *args, **kwargs)
        return self.cursor

    def start_fn(
        self,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        self.cursor = self.start_fn_in_executor(self.mainExec, fn, *args, **kwargs)
        return self.cursor

    def start_fn_after_cursor(
        self,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        self.cursor = self.start_fn_after_future(self.cursor, fn, *args, **kwargs)
        return self.cursor

    def start_fns_after_future(
        self,
        f: Future[Any],
        fns: list[Callable[P, T]],
        alist: list[Iterable[Any] | Any] = [],
        kwalist: list[Mapping[str, Any]] = [],
    ) -> Future[T]:
        if not alist:
            for _ in range(len(fns)):
                alist.append(())
        if not kwalist:
            for _ in range(len(fns)):
                kwalist.append({})
        ret = []
        for i, fn in enumerate(fns):
            ret.append(self.start_fn_after_future(f, fn, *alist[i], **kwalist[i]))
        self.cursor = self.merge_futures_list(ret)
        return self.cursor

    def start_fn_after_future(
        self,
        f: Future[Any],
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        def call_fn_after_future(
            f: Future[Any],
            fn: Callable[P, T],
            *args: Iterable[Any] | Any,
            **kwargs: Mapping[str, Any],
        ) -> T:
            while not f.done():
                pass
            return fn(*args, **kwargs)

        self.cursor = self.mainExec.submit(call_fn_after_future, f, fn, *args, **kwargs)
        return self.cursor

    def start_fn_after_futures_list(
        self,
        l: FList,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        f = self.merge_futures_list(l)
        self.cursor = self.start_fn_after_future(f, fn, *args, **kwargs)
        return self.cursor

    def merge_futures_list(self, l: FList) -> FList:
        def merge(l: FList) -> list[Any]:
            while not self.__all_futures_done(l):
                pass
            return [x.result() for x in l]

        return self.mainExec.submit(merge, l)

    def __all_futures_done(self, futures: FList) -> bool:
        return all(x.done() for x in futures)


class PollingAgent:
    logger = logging.getLogger(__name__)
    raemis: Raemis
    genis: GenieACS
    sonar: Sonar
    ue: list[UE]
    __devices: list
    pipeline: Pipeline = Pipeline()

    def __init__(self):
        self.logger.info("starting polling agent")
        self.raemis = Raemis()
        self.genie = GenieACS()
        self.sonar = Sonar()
        self.__startup()

    def __startup(self):
        f0 = self.__get_users_from_raemis()
        f1 = self.__get_devices_from_genie()
        f = self.pipeline.merge_futures_list([f0, f1])
        f = self.pipeline.start_fn_after_future(f, self.__integrate_devices)
        f = self.pipeline.start_fns_after_future(
            f, [self.__guess_with_raemis_data, self.__get_ip_from_raemis]
        )
        f = self.pipeline.start_fn_after_future(f, self.__run_snmp_info)
        f = self.pipeline.start_fn_after_future(f, self.__check_http_for_remaining)
        f = self.pipeline.start_fn_after_future(f, self.__baicells_web_scrapes)
        f = self.pipeline.start_fn_after_future(f, self.__get_sonar_info)
        self.pipeline.start_fn_after_future(
            f, lambda: self.logger.info("finished initializing")
        )

    def __baicells_web_scrapes(self) -> list[UE]:
        def fn(u: UE) -> UE:
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
            self.logger.info(f"Baicells mac address {mac} assigned to {str(u)}")
            return u

        u = [
            x
            for x in self.ue
            if x.manufacturer == UEManufacturer.BAICELLS
            and x.ipv4 is not None
            and x.mac_address is None
        ]

        self.logger.warn("web scraping baicells")
        return list(self.pipeline.map(lambda x: fn(x), u))

    def __check_http_for_remaining(self):
        def fn(u: UE):
            bec = BECWebEmulator(f"http://{str(u.ipv4)}")
            m = bec.is_bec()
            if m:
                u.manufacturer = UEManufacturer.BEC
                if "6900" in m:
                    u.model = UEModel.BEC6900
                elif "6500" in m:
                    u.model = UEModel.BEC6500
                elif "7000" in m:
                    u.model = UEModel.BEC7000
                else:
                    u.model = UEModel.BEC6900

        left = list(filter(lambda x: x.model == UEModel.WAC104, self.ue))
        return list(self.pipeline.map(lambda x: fn(x), left))

    def __get_sonar_info(self):
        self.logger.warn("getting sonar data")
        inv = self.pipeline.start_fn(self.sonar.get_inventory_items)
        names = self.pipeline.start_fn(self.sonar.get_account_id_and_name)
        inv.add_done_callback(self.__assign_sonar_inventory_info)
        names.add_done_callback(self.__guess_sonar_names)

    def update_sonar_inventory_assignments(self) -> Future[list[dict[str, Any]]]:
        return self.pipeline.start_fn(self.__assign_ue_to_sonar_addresses)

    def update_sonar_inventory_assignment(self, u: UE) -> Future[dict[str, Any]]:
        self.logger.info(f"assigning UE to client: {str(u)}")
        return self.pipeline.start_fn(self.sonar.assign_inventory_item, u)

    def __assign_ue_to_sonar_addresses(self) -> list[dict[str, Any]]:
        m = self.pipeline.map(lambda x: self.sonar.assign_inventory_item(x), self.ue)
        return list(m)

    def __guess_sonar_names(self, f: Future[list[AccountType] | None]):
        self.logger.info("linking sonar_ids to client data")
        while not f.done():
            pass
        a = f.result()
        if a is None:
            self.logger.error("no account and address information available")
            return

        def fn_ue(ue: UE):
            if a is None:
                return
            if ue.client is None or not ue.client.name:
                self.logger.error(
                    f"UE (IMEI: {ue.imei}, sonar_id: {ue.sonar_id}) does not have an attached client or does not have a name for the client"
                )
                return
            try:
                aan = list(
                    filter(
                        lambda x: ue.client
                        and ue.client.name
                        and "name" in x
                        and all(
                            list(
                                map(
                                    lambda y: y.lower() in x["name"].lower(),
                                    re.sub(
                                        """\s+""",
                                        """ """,
                                        ue.client.name.lower().replace("&", "").strip(),
                                    ).split(" "),
                                )
                            )
                        ),
                        a,
                    )
                )

                if len(aan) < 1:
                    self.logger.error(
                        f"could not find a matching name in sonar for {ue.client.name}"
                    )
                    return
                if len(aan) > 1:
                    self.logger.warn(
                        f'{ue.client.name} matched multiple names in sonar going with the first match: {aan[0]["name"]}'
                    )
                aan = aan[0]
            except:
                if ue.client and ue.client.name:
                    self.logger.error(
                        f"no sonar name that matches the raemis name: {ue.client.name}"
                    )
                else:
                    self.logger.error(f"no raemis names")
                return
            self.logger.info(
                f'found sonar_id: {aan["id"]} for client {ue.client.name} (name in sonar: {aan["name"]})'
            )
            ue.client.sonar_id = aan["id"]
            if ue.client.address is None:
                ue.client.address = Address()
            address = aan["addresses"]["entities"]
            if not address or len(address) < 1:
                self.logger.warn(f"sonar does not have address for {ue.client.name}")
                return
            address = address[0]
            ue.client.address.sonar_id = address["id"]
            ue.client.address.line1 = address["line1"]
            ue.client.address.line2 = address["line2"]
            ue.client.address.city = address["city"]
            ue.client.address.zip_code = address["zip"]
            self.logger.info(
                f'found sonar_id: {address["id"]} for {ue.client.name}\'s address at {", ".join([ue.client.address.line1,ue.client.address.city,ue.client.address.zip_code])}'
            )

        return list(self.pipeline.map(lambda x: fn_ue(x), self.ue))

    def __assign_sonar_inventory_info(self, f: Future[list[InventoryType] | None]):
        self.logger.warn("linking sonar_ids to UE info")

        def fn(ue: InventoryType):
            if ue is None:
                return
            sonar_id = ue["id"]
            mac_address = None
            fields = ue["inventory_model_field_data"]
            if fields is not None:
                fields = fields["entities"]
                for field in fields:
                    if "mac" in field["inventory_model_field"]["name"].lower():
                        mac_address = field["value"]
            model = ue["inventory_model"]
            if model is not None:
                sonar_model_id = model["id"]
                sonar_model = model["name"]
            if mac_address is not None:
                ue = self.__get_ue_by_mac(MACAddress(mac_address.upper()))
                if ue is None:
                    self.logger.error(
                        f"unable to find ue for mac address {str(mac_address)}"
                    )
                    return
                self.logger.info(
                    f"assigning sonar_id: {sonar_id} to UE with IMEI: {ue.imei} and MAC Address: {str(mac_address)}"
                )
                ue.sonar_id = sonar_id

        while not f.done():
            pass
        i = f.result()
        if i is not None:
            return list(self.pipeline.map(lambda x: fn(x), i))

    def __get_ue_by_mac(self, mac: MACAddress) -> UE | None:
        try:
            return next(
                filter(
                    lambda x: x
                    and x.mac_address
                    and x.mac_address.get().upper() == mac.get().upper(),
                    self.ue,
                )
            )
        except:
            return None

    def __get_ue_by_client_name(self, name: str) -> UE | None:
        try:
            return next(
                filter(
                    lambda x: x
                    and x.client
                    and x.client.name
                    and x.client.name == name,
                    self.ue,
                )
            )
        except:
            return None

    def __get_ip_from_raemis(self):
        self.logger.warn("getting ips from raemis")
        data = self.raemis.get_data_sessions()
        if data is None:
            return

        def f(ue: UE):
            if data is None:
                return
            d = next(
                x
                for x in data
                if "imsi" in x
                and hasattr(ue, "imsi")
                and ue.imsi
                and x["imsi"] == ue.imsi
            )
            if d is None:
                self.logger.warn(
                    f"unable to find data connection in Raemis for IMSI: {ue.imsi}"
                )
                return
            if "ip" in d and isinstance(d["ip"], str) and "." in d["ip"]:
                self.logger.debug(f'assigning IP address {d["ip"]} to IMSI: {ue.imsi}')
                ue.set_host(IPv4Address(address=d["ip"]))
            ue.apn = d["apn"] if "apn" in d else None

        return list(self.pipeline.map(lambda x: f(x), self.ue))

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

    def __run_snmp_info(self):
        def f(ue: UE) -> None:
            if not ue._snmp:
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
                self.logger.debug(
                    f"found MAC address {str(ue.mac_address)} for UE with IMEI: {ue.imei}"
                )

        l = list(self.pipeline.map(lambda x: f(x), self.ue))
        self.logger.warn(
            f"found {len([x for x in self.ue if x.mac_address])} UE mac addresses"
        )
        return l

    def __guess_with_raemis_data(self) -> list:
        def f(ue: UE) -> None:
            name = self.__guess_client_name(ue)
            manufacturer = self.__guess_ue_manufacturer(ue)
            model = self.__guess_ue_model(ue)
            ue.client.name = name
            ue.manufacturer = manufacturer
            ue.model = model
            self.logger.debug(
                f"for UE IMEI: {ue.imei} found name: {name}, manufacturer: {str(manufacturer.value)}, model: {str(model.value)}"
            )

        return list(self.pipeline.map(lambda x: f(x), self.ue))

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

    def __get_users_from_raemis(self) -> Future:
        self.logger.info("getting raemis subscribers")
        ueFuture = self.pipeline.start_fn(self.raemis.get_subscribers)
        ueFuture.add_done_callback(self.__set_ue)
        return ueFuture

    def __get_devices_from_genie(self) -> Future:
        self.logger.info("getting genie devices")
        deviceFuture = self.pipeline.start_fn(self.genie.get_devices)
        deviceFuture.add_done_callback(self.__set_devices)
        return deviceFuture

    def __integrate_devices(self) -> FList:
        self.logger.info("integrating genie data into UE records")
        tasks = []
        for device in self.__devices:
            t = self.pipeline.start_fn(self.__integrate_device, device)
            tasks.append(t)
        task = self.pipeline.merge_futures_list(tasks)
        return task

    def __integrate_device(self, device: Any) -> UE | None:
        currUE = None
        if hasattr(device, "InternetGatewayDevice"):
            igd = device.InternetGatewayDevice
            if hasattr(igd, "WANDevice"):
                wd = igd.WANDevice
                if hasattr(wd, "item1"):
                    i1 = wd.item1
                    if hasattr(i1, "WANConnectionDevice"):
                        wcd = i1.WANConnectionDevice
                        if hasattr(wcd, "item1"):
                            i01 = wcd.item1
                            if hasattr(i01, "WANIPConnection"):
                                wipc = i01.WANIPConnection
                                if hasattr(wipc, "item1"):
                                    i001 = wipc.item1
                                    if (
                                        hasattr(i001, "MACAddress")
                                        and i001.MACAddress
                                        and ":" in i001.MACAddress
                                    ):
                                        currUE = filter(
                                            lambda x: x.mac_address
                                            and x.mac_address.get() == i001.MACAddress,
                                            self.ue,
                                        )
                                        currUE = list(currUE)
                                        if len(currUE) > 1:
                                            self.logger.error(
                                                "found multiple UE with the same MAC address in the UE list"
                                            )
                                            raise LookupError
                                        elif len(currUE) == 1:
                                            currUE = currUE[0]
                                            currUE.mac_address = MACAddress(
                                                i001.MACAddress
                                            )
                                        else:
                                            currUE = None
                    elif hasattr(i1, "WANNetConfigInfo"):
                        wnci = i1.WANNetConfigInfo
                        if hasattr(wnci, "IMEI"):
                            imei = wnci.IMEI
                            currUE = list(
                                filter(lambda x: x.imei and x.imei == imei, self.ue)
                            )
                            if len(currUE) > 1:
                                self.logger.error(
                                    "found multiple UE with the same IMEI"
                                )
                                raise LookupError
                            elif len(currUE) == 1:
                                u: UE = currUE[0]
                                u.cell_id = (
                                    u.cell_id
                                    if u.cell_id
                                    else (
                                        wnci.CellId if hasattr(wnci, "CellId") else ""
                                    )
                                )
                                u.bandwidth = (
                                    u.bandwidth
                                    if u.bandwidth
                                    else (
                                        wnci.Bandwidth
                                        if hasattr(wnci, "Bandwidth")
                                        else ""
                                    )
                                )
                                u.earfcn = (
                                    u.earfcn
                                    if u.earfcn
                                    else (
                                        wnci.Earfcn if hasattr(wnci, "Earfcn") else ""
                                    )
                                )
                                u.mcc = (
                                    u.mcc
                                    if u.mcc
                                    else (wnci.MCC if hasattr(wnci, "MCC") else "")
                                )
                                u.mnc = (
                                    u.mnc
                                    if u.mnc
                                    else (wnci.MNC if hasattr(wnci, "MNC") else "")
                                )
                                u.rssi = (
                                    u.rssi
                                    if u.rssi
                                    else (wnci.RSSI if hasattr(wnci, "RSSI") else "")
                                )
                                u.rsrp = (
                                    u.rsrp
                                    if u.rsrp
                                    else (wnci.RSRP if hasattr(wnci, "RSRP") else "")
                                )
                                u.rsrq = (
                                    u.rsrq
                                    if u.rsrq
                                    else (wnci.RSRQ if hasattr(wnci, "RSRQ") else "")
                                )
                                u.rssi = (
                                    u.rssi
                                    if u.rssi
                                    else (wnci.RSSI if hasattr(wnci, "RSSI") else "")
                                )
                                u.sinr = (
                                    u.sinr
                                    if u.sinr
                                    else (wnci.SINR if hasattr(wnci, "SINR") else "")
                                )
                                u.eci = (
                                    u.eci
                                    if u.eci
                                    else (wnci.ECI if hasattr(wnci, "ECI") else "")
                                )
                                u.tx_power = (
                                    u.tx_power
                                    if u.tx_power
                                    else (
                                        wnci.TxPower if hasattr(wnci, "TxPower") else ""
                                    )
                                )
                                u.tx_rate = (
                                    u.tx_rate
                                    if u.tx_rate
                                    else (
                                        wnci.TxDataRate
                                        if hasattr(wnci, "TxDataRate")
                                        else ""
                                    )
                                )
                                u.tx_mcs = (
                                    u.tx_mcs
                                    if u.tx_mcs
                                    else (
                                        wnci.UplinkMcs
                                        if hasattr(wnci, "UplinkMcs")
                                        else ""
                                    )
                                )
                                u.rx_power = (
                                    u.rx_power
                                    if u.rx_power
                                    else (
                                        wnci.RxPower if hasattr(wnci, "RxPower") else ""
                                    )
                                )
                                u.rx_rate = (
                                    u.rx_rate
                                    if u.rx_rate
                                    else (
                                        wnci.RxDataRate
                                        if hasattr(wnci, "RxDataRate")
                                        else ""
                                    )
                                )
                                u.rx_mcs = (
                                    u.rx_mcs
                                    if u.rx_mcs
                                    else (
                                        wnci.DownlinkMcs
                                        if hasattr(wnci, "DownlinkMcs")
                                        else ""
                                    )
                                )
                                u.signal_quality = (
                                    u.signal_quality
                                    if u.signal_quality
                                    else (
                                        wnci.SignalQuality
                                        if hasattr(wnci, "SignalQuality")
                                        else ""
                                    )
                                )

        return currUE

    def get_sonar_name_no_sonar_address(self):
        return list(
            filter(
                lambda x: x.client
                and x.client.sonar_id
                and (not x.client.address or not x.client.address.sonar_id),
                self.ue,
            )
        )

    def get_sonar_devices_no_sonar_client_or_no_sonar_address(self):
        return list(
            filter(
                lambda x: x.sonar_id
                and (
                    (x.client and not x.client.sonar_id)
                    or (x.client.address and not x.client.address.sonar_id)
                ),
                self.ue,
            )
        )

    def get_raemis_name_no_sonar_name(self):
        return list(
            filter(
                lambda x: x.client and x.client.name and not x.client.sonar_id, self.ue
            )
        )

    def get_raemis_devices_no_sonar_device(self):
        return list(filter(lambda x: not x.sonar_id and (x.imei or x.imsi), self.ue))

    def get_all_devices_no_mac(self):
        return list(
            filter(
                lambda x: (x.imei or x.imsi) and x.ipv4 and not x.mac_address, self.ue
            )
        )

    def get_raemis_devices_with_no_sonar_match_and_with_sonar_name(self):
        return list(
            filter(lambda x: not x.sonar_id and x.client and x.client.sonar_id, self.ue)
        )

    def get_raemis_device_with_no_sonar_match_and_with_sonar_address(self):
        return list(
            filter(
                lambda x: not x.sonar_id
                and x.client
                and x.client.address
                and x.client.address.sonar_id,
                self.ue,
            )
        )

    def __set_devices(self, devices: Future[list]) -> None:
        while not devices.done():
            pass
        self.__devices = devices.result()

    def __set_ue(self, ue: Future[list[UE]]) -> None:
        while not ue.done():
            pass
        self.ue = ue.result()
