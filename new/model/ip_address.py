#!/usr/bin/env python3

import logging
from functools import reduce
from re import compile, fullmatch


class IPv4Address:
    logger = logging.getLogger(__name__)
    address: list[int]
    netmask: list[int]
    cidr_mask: int

    def __init__(
        self,
        *,
        address: str = "",
        octets: list[int] = [],
        cidr_mask: int = 32,
        netmask: list[int] = [],
    ):
        if not (address or octets):
            self.logger.error("Must provide an IP address in string or list form")
            raise ValueError

        if address:
            if not fullmatch(compile("""(\d{,2}[1-9].){3}\d{,2}[1-9]"""), address):
                self.logger.error(
                    f"Provided string, {address} is not in the (PCRE) form of (\\d{{1,3}}){{4}}"
                )
            try:
                self.address = list(map(lambda x: int(x), address.split(".")))
            except:
                self.logger.error(
                    f"The provided string, {address}, has one or more grops of characters that cannot parse as an integer"
                )
                raise ValueError

        if octets:
            try:
                self.address = list(map(lambda x: int(x), octets))
            except:
                self.logger.error(
                    f"The provided list, {octets}, has one or more grops of characters that cannot parse as an integer"
                )
                raise ValueError

        if not netmask:
            netmask = self.cidr_to_netmask(cidr_mask)

        if not self.is_valid_netmask(netmask=netmask):
            self.logger.error("invalid netmask provided")
            raise ValueError

        if not self.is_valid_ipv4(self.address, netmask=netmask):
            self.logger.error("ipv4 adddress/netmask combo invalid, see warning logs")
            raise ValueError

        self.netmask = netmask
        self.cidr_mask = self.netmask_to_cidr(self.netmask)

    @classmethod
    def is_valid_ipv4(
        cls, addr: list[int], *, cidr: int = 0, netmask: list[int] = []
    ) -> bool:
        if not (cidr or netmask):
            cls.logger.warn("No netmask provided, using /32")
            netmask = cls.cidr_to_netmask(32)
        if cidr and netmask:
            cls.logger.warn(
                "was given both a CIDR mask and a netmask address, using the CIDR mask"
            )
        if cidr:
            netmask = cls.cidr_to_netmask(cidr)

        if not cls.is_valid_netmask(netmask=netmask):
            cls.logger.error("Invalid netmask, check warning logs")
            raise AttributeError

        if len(addr) != 4:
            return False
        if len(list(filter(lambda x: x.bit_length() > 8 or x < 1, addr))):
            return False

        network = [addr[a] & m for a, m in enumerate(netmask)]
        broadcast = [addr[a] | (0xFF ^ m) for a, m in enumerate(netmask)]

        if (addr == broadcast or addr == network) and cls.netmask_to_cidr(
            netmask
        ) != 32:
            cls.logger.warn("ip address cannot be the network or broadcast address")
            return False

        if not all([v >= network[i] and v <= broadcast[i] for i, v in enumerate(addr)]):
            cls.logger.warn("ip address must be within the network")
            return False

        return True

    @classmethod
    def is_valid_netmask(cls, *, cidr: int = 0, netmask: list[int] = []) -> bool:
        if not (cidr or netmask):
            cls.logger.error("Either a CIDR mask or a netmask address msut be provided")
            raise AttributeError
        if cidr and netmask:
            cls.logger.warn(
                "was given both a CIDR mask and a netmask address, using the CIDR mask"
            )
        if cidr:
            netmask = cls.cidr_to_netmask(cidr)
        if len(netmask) != 4:
            cls.logger.warn("provided netmask must have 4 octets")
            return False
        if len(list(filter(lambda x: x.bit_length() > 8 or x < 1, netmask))):
            cls.logger.warn(
                "netmask octet values must be integers in the range [1,255]"
            )
            return False
        #
        # An octet in a CIDR netmask (according to RFC 1219) must have contiguous subnet bits ("1"s) starting
        # from the most siginificant bit working towards the least significant bit.
        #
        # A number, x, that is a member of the set of natural numbers that has a binary representation
        # with contiguous "1"s starting from the most significant bit to the least significant bit that is a "1"
        # will always satisfy the following expression
        #
        #      n, m | n, m in N
        #      length(m_2) -> the minimum number of binary digits that can be used to represent the number m in binary
        #      ones(m_2) -> the number of binary digits that are "1" in the binary representation of the number m
        #      n == 2^(length(n_2)) - 2^(length(n_2) - (ones(n_2))) --> True
        #
        # Therefore, if a natural number, n, does not satisfy the above expression, it is an invalid octet in a
        # CIDR netmask
        #
        #
        if len(
            list(
                filter(
                    lambda x: 2 ** x.bit_length() - 2 ** cls.__ones(x) != x,
                    netmask,
                )
            )
        ):
            cls.logger.warn("octets in the netmask must be in CIDR form, see RFC 1219")
            return False
        if sorted(netmask, reverse=True) != netmask:
            cls.logger.warn("netmask octets must be in descending sorted order")
            return False
        return True

    @classmethod
    def netmask_to_cidr(cls, netmask: list[int]) -> int:
        if not cls.is_valid_netmask(netmask=netmask):
            cls.logger.error("invalid netmask")
            raise ValueError
        return sum([v << 8 * (3 - i) for i, v in enumerate(netmask)]).bit_count()

    @classmethod
    def cidr_to_netmask(cls, cidr_mask: int) -> list[int]:
        if cidr_mask < 2 or cidr_mask > 32:
            cls.logger.error(f"A CIDR netmask must be between 2 and 32, inclusive.")
            raise ValueError

        bitmask = (2**cidr_mask) - 1 << (32 - cidr_mask)

        netmask = [((0xFF << 8 * x) & bitmask) >> 8 * x for x in range(3, -1, -1)]

        if not cls.is_valid_netmask(netmask=netmask):
            cls.logger.error(
                "the netmask address generated from this CIDR netmask had problems"
            )
            raise ValueError
        return netmask

    @classmethod
    def __ones(cls, x: int) -> int:
        return x.bit_length() - x.bit_count()
