#!/usr/bin/env python3

from typing_extensions import Self as _Self
import logging
import re as _re


class IPv4Address:
    logger = logging.getLogger(__name__)
    address: tuple[int, int, int, int]
    netmask: tuple[int, int, int, int]
    cidr_mask: int

    def __init__(
        self,
        *,
        address: str = None,
        octets: tuple[int, int, int, int] | None = None,
        cidr_mask: int = 32,
        netmask: tuple[int, int, int, int] | None = None,
    ):
        if not (address or octets):
            self.logger.error("Must provide an IP address in string or list form")
            raise ValueError

        if address:
            address = address.strip()
            if not _re.match(_re.compile(r"""(\d{1,3}\.){3}\d{1,3}"""), address):
                self.logger.error(
                    f"Provided string, {address} is not in the (PCRE) form of (\\d{{1,3}}.){{3}}\\d{{1,3}}"
                )
            try:
                self.address = tuple(map(lambda x: int(x), address.split(".")))
            except:
                self.logger.error(
                    f"The provided string, {address}, has one or more grops of characters that cannot parse as an integer"
                )
                raise ValueError

        if octets:
            try:
                self.address = tuple(map(lambda x: int(x), octets))
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

    @property
    def network(self) -> tuple[int, int, int, int]:
        return tuple(self.address[a] & m for a, m in enumerate(self.netmask))

    @property
    def broadcast(self) -> tuple[int, int, int, int]:
        return tuple(self.address[a] | (0xFF ^ m) for a, m in enumerate(self.netmask))

    @classmethod
    def is_valid_ipv4(
        cls,
        addr: tuple[int, int, int, int],
        *,
        cidr: int = 0,
        netmask: tuple[int, int, int, int] | None = None,
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
        elif netmask is None:
            netmask = (255, 255, 255, 255)

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
    def is_valid_netmask(
        cls, *, cidr: int = 0, netmask: tuple[int, int, int, int] | None = None
    ) -> bool:
        if not (cidr or netmask):
            cls.logger.error("Either a CIDR mask or a netmask address msut be provided")
            raise AttributeError
        if cidr and netmask:
            cls.logger.warn(
                "was given both a CIDR mask and a netmask address, using the CIDR mask"
            )
        if cidr:
            netmask = cls.cidr_to_netmask(cidr)
        elif netmask is None:
            netmask = (255, 255, 255, 255)
        if len(netmask) != 4:
            cls.logger.warn("provided netmask must have 4 octets")
            return False
        if len(list(filter(lambda x: x.bit_length() > 8 or x < 0, netmask))):
            cls.logger.warn(
                "netmask octet values must be integers in the range [0,255]"
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
            tuple(
                filter(
                    lambda x: 2 ** x.bit_length() - 2 ** cls.__ones(x) != x,
                    netmask,
                )
            )
        ):
            cls.logger.warn("octets in the netmask must be in CIDR form, see RFC 1219")
            return False
        if tuple(sorted(netmask, reverse=True)) != netmask:
            cls.logger.warn("netmask octets must be in descending sorted order")
            return False
        return True

    @classmethod
    def netmask_to_cidr(cls, netmask: tuple[int, int, int, int]) -> int:
        if not cls.is_valid_netmask(netmask=netmask):
            cls.logger.error("invalid netmask")
            raise ValueError
        return sum([v << 8 * (3 - i) for i, v in enumerate(netmask)]).bit_count()

    @classmethod
    def cidr_to_netmask(cls, cidr_mask: int) -> tuple[int, int, int, int]:
        if cidr_mask < 2 or cidr_mask > 32:
            cls.logger.error(f"A CIDR netmask must be between 2 and 32, inclusive.")
            raise ValueError

        bitmask = (2**cidr_mask) - 1 << (32 - cidr_mask)

        netmask = tuple(((0xFF << 8 * x) & bitmask) >> 8 * x for x in range(3, -1, -1))

        if not cls.is_valid_netmask(netmask=netmask):
            cls.logger.error(
                "the netmask address generated from this CIDR netmask had problems"
            )
            raise ValueError
        return netmask

    @classmethod
    def __ones(cls, x: int) -> int:
        return x.bit_length() - x.bit_count()

    def __str__(self) -> str:
        a = self.address
        return f"{a[0]}.{a[1]}.{a[2]}.{a[3]}/{self.cidr_mask}"

    def __repr__(self) -> str:
        a = self.address
        return f"{a[0]}.{a[1]}.{a[2]}.{a[3]}/{self.cidr_mask}"

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, IPv4Address):
            return False
        return self.address == __o.address and self.cidr_mask == __o.cidr_mask

    def __hash__(self) -> int:
        return hash(str(self))

    def __contains__(self, __o: object) -> bool:
        if not isinstance(__o, IPv4Address):
            return False
        return self.network == __o.network


class MACAddress:
    def __init__(self, mac: str) -> None:
        if not isinstance(mac, str):
            raise ValueError()
        mac = mac.upper().replace(":", "")
        if len(mac) != 12:
            raise ValueError()
        self.mac = bytes.fromhex(mac)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, MACAddress):
            return False
        return str(self) == str(__o)

    def __hash__(self) -> int:
        return hash(str(self))

    def __repr__(self) -> str:
        return bytes.hex(self.mac, ":", 1).upper()

    def __str__(self) -> str:
        return bytes.hex(self.mac, ":", 1).upper()


class IMEI(str):
    __log = logging.getLogger(__name__)

    def __new__(cls, obj: object = "") -> _Self:
        s = super(IMEI, cls).__new__(cls, obj).strip().replace("-", "")
        if len(s) not in (15, 16):
            cls.__log.error(
                f"provided {s}, but IMEI must be 15 characters long (or 16 for newer versions)"
            )
            raise ValueError
        if not s.isdecimal():
            cls.__log.error(
                f"provided {s}, but IMEI must be a string of decimal numbers"
            )
            raise ValueError
        return s


class IMSI(str):
    __log = logging.getLogger(__name__)

    def __new__(cls, obj: object = "") -> _Self:
        s = super(IMSI, cls).__new__(cls, obj).strip()
        if len(s) != 15:
            cls.__log.error(f"provided {s}, but IMSI must be 15 characters long")
            raise ValueError
        if not s.isdecimal():
            cls.__log.error(
                f"provided {s}, but IMSI must be a string of decimal numbers"
            )
            raise ValueError
        return s
