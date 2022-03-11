#!/usr/bin/env python3

import logging
from re import compile, fullmatch


class IPv4Address:
    def __init__(
        self,
        *,
        address: str = "",
        octets: list[int] = [],
        cidr_mask: int = 32,
        netmask: str = "",
    ):
        logging.getLogger(__name__)
        if not (address or octets):
            logging.error("Must provide an IP address in string or list form")
            raise ValueError
        if address:
            if not fullmatch(compile("""(\d{,2}[1-9].){3}\d{,2}[1-9]"""), address):
                logging.error(
                    f"Provided string, {address} is not in the (PCRE) form of (\\d{{1,3}}){{4}}"
                )
            try:
                self.octets = list(map(lambda x: int(x), address.split(".")))
            except:
                logging.error(
                    f"The provided string, {address}, has one or more grops of characters that cannot parse as an integer"
                )
                raise ValueError
        if octets:
            try:
                self.octets = list(map(lambda x: int(x), octets))
            except:
                logging.error(
                    f"The provided list, {octets}, has one or more grops of characters that cannot parse as an integer"
                )

    @staticmethod
    def cidr_to_netmask(cidr_mask: int):
        netmask = int(f'{"1" * cidr_mask}{"0" * (32-cidr_mask)}', 2)
        return netmask

    def is_valid_ipv4(self):
        pass
