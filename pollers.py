#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import time
from functools import partial
from os import environ
import operator
import shlex
import asyncio
import random
import asyncio.subprocess
from dataclasses import KW_ONLY, dataclass, field
import json
from json.decoder import JSONDecoder
import logging
from pprint import pprint
from typing import Collection, Iterable, Mapping, Any, Callable, Type
from aiohttp.client import ClientSession, ClientTimeout
from main import Application
import aiohttp
import shutil

from model.network import IPv4Address


@dataclass(frozen=True)
class OID:
    oid_str: str


@dataclass
class MonitoringTemplate:
    """A container for the Sonar Monitoring Template (SNMPv2 only)."""

    template_id: str = field(kw_only=True, default="")
    oids: Collection[OID] = field(kw_only=True, default=frozenset())
    icmp: bool = field(kw_only=True, default=False)
    interface_stats: bool = field(kw_only=True, default=False)
    snmp_version: int = field(kw_only=True, default=2)
    snmp_community: str = field(kw_only=True, default="public")

    def __post_init__(self):
        if self.template_id is not None:
            self.template_id = str(self.template_id)
        if self.snmp_version is not None:
            self.snmp_version = int(self.snmp_version)


@dataclass
class PingResult:
    host: IPv4Address | None = field(default=None, init=True)
    pings: list[float] | None = field(default=None)
    num_failures: int = field(default=0)
    status_code: int = field(default=0)
    error_msg: str | None = field(default=None)


@dataclass
class PollerRequest:

    _: KW_ONLY
    item_id: str
    ip: IPv4Address
    host_type: str
    priority: int
    template: MonitoringTemplate
    snmp_overrides: Iterable = field(default=frozenset(), hash=False, init=False)
    icmp_result: PingResult = field(default=PingResult(), hash=False, init=False)

    def __post_init__(self):
        if self.priority is not None:
            self.priority = int(self.priority)
        if isinstance(self.ip, str):
            self.ip = IPv4Address(address=self.ip)


_parsing_type = (
    Collection[PollerRequest]
    | PollerRequest
    | Collection[MonitoringTemplate]
    | MonitoringTemplate
)


def json_obj_hook(pairs: dict[str, Any]) -> _parsing_type:
    """Called for every sub-dict"""
    if all(
        map(
            lambda x: x in pairs,
            ["ip", "type", "polling_priority", "monitoring_template_id"],
        )
    ):
        return PollerRequest(
            item_id="",
            ip=IPv4Address(address=pairs["ip"]),
            host_type=pairs["type"],
            template=MonitoringTemplate(template_id=pairs["monitoring_template_id"]),
            priority=pairs["polling_priority"],
        )
    elif all(map(lambda x: isinstance(x, PollerRequest), pairs.values())):
        ret = list()
        for item_id in pairs:
            pairs[item_id].item_id = item_id
            ret.append(pairs[item_id])
        return ret
    elif all(
        map(
            lambda x: x in pairs,
            ["icmp", "collect_interface_statistics", "snmp_community", "oids"],
        )
    ):
        return MonitoringTemplate(
            icmp=pairs["icmp"],
            interface_stats=pairs["collect_interface_statistics"],
            snmp_version=pairs["snmp_version"],
            snmp_community=pairs["snmp_community"],
            oids=set(map(OID, pairs["oids"])),
        )
    elif all(map(lambda x: isinstance(x, MonitoringTemplate), pairs.values())):
        ret = list()
        for template_id in pairs:
            pairs[template_id].template_id = template_id
            ret.append(pairs[template_id])
        return ret
    elif "hosts" in pairs and "template" in pairs:
        hosts: list[PollerRequest] = pairs["hosts"]
        templates: list[MonitoringTemplate] = pairs["template"]
        for host in hosts:
            try:
                host.template = next(
                    template
                    for template in templates
                    if template.template_id == host.template.template_id
                )
            except:
                raise ValueError
        return hosts
    elif "hosts" in pairs:
        return pairs["hosts"]
    elif "data" in pairs:
        return pairs["data"]
    else:
        raise LookupError


class ICMPPoller:

    log = logging.getLogger(__name__)
    requests: Collection[PollerRequest]
    time_taken: float = -1

    def __init__(self, requests: Collection[PollerRequest]) -> None:
        self.requests = requests

    def run_all_pings(self) -> None:
        asyncio.run(self.ping_all())

    async def ping_all(self) -> None:
        results = []
        for request in self.requests:
            results.append(asyncio.create_task(self.fping(request)))
        await asyncio.gather(*results)

    def _get_fping_cmd(
        self, host: IPv4Address, repeats: int, timeout: int
    ) -> list[str]:
        if host is None or repeats == 0 or timeout == 0:
            self.log.error(
                f"Invalid value for parameter(s) host: {str(host)}, num pings: {repeats}, timeout: {timeout}"
            )
            raise ValueError
        path = shutil.which("fping")
        if path is None:
            self.log.error(f"unable to find fping in $PATH")
            raise FileNotFoundError
        interval = random.randrange(500, 1000)
        return shlex.split(
            f"{shlex.quote(path)} -C {repeats} -t {timeout} -b 12 -p {interval} -r 0 -B 1.5 -R {repr(host)}"
        )

    # lazily parse results into usable numbers
    def filter_fails(self, results: list[str]) -> list[float]:
        return list(
            map(
                # convert the non-error values to real numbers
                lambda n: float(n[1]),
                filter(
                    # filter tuples where not all members are numbers (execption checking filter)
                    lambda b: b[0],
                    map(
                        # return tuple -> (bool::all members of `t` are numbers, str::join each elem of `t` by `.`)
                        lambda t: (all(map(str.isdecimal, t)), ".".join(t)),
                        # where `t` is an array formed by spliting `res_list` by a decimal point
                        map(lambda s: s.split("."), results),
                    ),
                ),
            )
        )

    # return the number of failures
    def count_fails(self, res_list: list[str]) -> int:
        return len(set(filter(bool, map(partial(operator.eq, "-"), res_list))))

    def _parse_fping_output(self, output: bytes) -> PingResult:
        str_output = output.decode().strip()
        res_list = str_output.split(" : ")[1].split()
        res_host = str_output.split()[0]
        # Count the number of failures
        num_loss = self.count_fails(res_list)
        # filter out failures and convert numbers
        ping_list = self.filter_fails(res_list)
        return PingResult(IPv4Address(address=res_host), ping_list, num_loss)

    async def fping(self, request: PollerRequest, repeats=10, timeout=2000) -> None:
        res = await asyncio.subprocess.create_subprocess_exec(
            *self._get_fping_cmd(request.ip, repeats, timeout),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        if res.stderr is None:
            self.log.error(f"Unable to connect to file descriptor for `fping` output")
            raise IOError
        output = await res.stderr.read(-1)
        status = await res.wait()
        await asyncio.sleep(0)
        if status != 0:
            self.log.error(f"`fping` returned status code {status}. Message: {output}")
            request.icmp_result = PingResult(
                request.ip, status_code=status, error_msg=output.decode()
            )
        request.icmp_result = self._parse_fping_output(output)


class PollerConnection:
    log = logging.getLogger(__name__)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": f"SonarPoller/{Application.config.poller.version}",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
        }

    @property
    def request_body(self) -> dict[str, str]:
        return {
            "api_key": Application.config.poller.key,
            "version": Application.config.poller.version,
        }

    def run(self):
        asyncio.run(self.do_task())

    async def do_task(self):
        poller = await self.get_requests()
        start = time.perf_counter()
        await poller.ping_all()
        stop = time.perf_counter()
        poller.time_taken = stop - start
        await self.send_response(poller)

    async def get_requests(self) -> ICMPPoller:
        async with aiohttp.ClientSession(
            headers=self.headers,
            timeout=ClientTimeout(connect=120, sock_read=120, sock_connect=120),
            trust_env=True,
        ) as session:
            async with session.post(
                url=Application.config.poller.request, json=self.request_body
            ) as resp:
                requests: list[PollerRequest] = await resp.json(
                    loads=JSONDecoder(object_hook=json_obj_hook).decode
                )
        await asyncio.sleep(0.250)
        return ICMPPoller(requests)

    async def send_response(self, poller: ICMPPoller):
        requests = poller.requests
        results: dict[str, dict[str, dict[str, float]]] = {}
        for request in requests:
            result = request.icmp_result
            if result.status_code != 0:
                self.log.error(
                    f"fping errored with status code {result.status_code}. Message: {result.error_msg}"
                )
                continue
            elif result.host is None or result.pings is None:
                self.log.error(f"No ICMP result found for request: {request}")
                continue
            results[request.item_id] = {
                "icmp": {
                    "low": min(result.pings),
                    "high": max(result.pings),
                    "median": sum(result.pings) / len(result.pings),
                    "loss_percentage": float(result.num_failures) / len(result.pings),
                }
            }
        self.log.debug(f"Results:\n{results}")
        ret: dict[str, Any] = dict(self.request_body)
        ret["time_taken"] = "%f.2" % poller.time_taken
        ret["results"] = results
        async with aiohttp.ClientSession(
            headers=self.headers,
            timeout=ClientTimeout(connect=120, sock_read=120, sock_connect=120),
            trust_env=True,
        ) as session:
            async with session.post(
                url=Application.config.poller.response, body=self.request_body
            ) as resp:
                status = await resp.json()
                self.log.info(f"Received response from Sonar: {status}")


if __name__ == "__main__":

    async def run():
        loaded = await asyncio.create_task(PollerConnection().get_requests())
        print(loaded)

    # asyncio.run(run())
    data = """
    {
    "data":{
    "hosts":{
    "12":{
    "ip": "1.1.1.1",
    "type":"site",
    "monitoring_template_id":1,
    "polling_priority":1
    },
    "16":{
    "ip": "8.8.8.8",
    "type":"site",
    "monitoring_template_id":1,
    "polling_priority":1
    },
    "15":{
    "ip": "8.8.4.4",
    "type":"site",
    "monitoring_template_id":1,
    "polling_priority":1
    },
    "14":{
    "ip": "127.0.0.1",
    "type":"site",
    "monitoring_template_id":1,
    "polling_priority":1
    },
    "13":{
    "ip": "10.11.11.1",
    "type":"site",
    "monitoring_template_id":1,
    "polling_priority":1
    }
    }
    }

     }
    """
    # test = ICMPPoller(data)
    loaded = json.loads(data, object_hook=json_obj_hook)

    async def go(num_runs):

        tasks = []
        start = time.perf_counter()
        for _ in range(num_runs):
            poller = ICMPPoller(loaded)
            tasks.append(poller.ping_all())
        await asyncio.gather(*tasks)
        end = time.perf_counter()
        return end - start

    RUNS = 10
    total = asyncio.run(go(RUNS))
    print(
        f"took: %.1fs total and averaged %.4fs over %s runs for %d hosts averaging %.4f per host for an average run"
        % (total, total / RUNS, RUNS, len(loaded), total / RUNS / len(loaded))
    )
