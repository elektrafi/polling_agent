#!/usr/bin/env python3


class MACAddress:
    def __init__(self, mac: str) -> None:
        if not isinstance(mac, str):
            raise ValueError()
        mac = mac.upper().replace(":", "")
        if len(mac) != 12:
            raise ValueError()
        self.mac = bytes.fromhex(mac).upper()

    def get(self) -> str:
        return str(self.mac).upper()

    def __eq__(self, other) -> bool:
        if isinstance(other, MACAddress):
            return self.mac == other.mac
        return False

    def __repr__(self):
        return bytes.hex(self.mac.upper(), ":", 1).upper()

    def __str__(self):
        return bytes.hex(self.mac.upper(), ":", 1).upper()
