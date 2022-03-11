#!/usr/bin/env python3
from dataclasses import dataclass
from . import MACAddress


@dataclass
class UE:
    mac_address: MACAddress
