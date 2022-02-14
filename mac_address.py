#!/usr/bin/env python3


class MACAddress:
    def __init__(self, mac: str) -> None:
        mac = mac.upper().replace(":", "")
        if len(mac) != 12:
            raise ValueError()
        self.mac = bytes.fromhex(mac)

    def get(self) -> bytes:
        return self.mac

    def __eq__(self, other) -> bool:
        if not isinstance(other, MACAddress):
            return False
        return self.mac == other

    def __repr__(self):
        return bytes.hex(self.mac, ":", 1)

    def __str__(self):
        return bytes.hex(self.mac, ":", 1)
