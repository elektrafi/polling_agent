#!/usr/bin/env python3

    def try_check_telrad_12000(self) -> bool:
        try:
            check = self._snmp_get(".1.3.6.1.4.1.17713.20.2.1.4.2.0")
            if check is None:
                return False
            check = check.value
            if check is None:
                return False
            return "12000" in check
        except:
            return False

    def get_bec_mac_address(self) -> _MACAddress | None:
        try:
            check = self.snmp.walk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "eth0"), None
            )
            mac = self._snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            self.has_snmp = False
            self.logger.error(
                f"SNMP for BEC {self.hostname} failed while matching eth0"
            )
            return None
        if not mac:
            return None
        mac = mac.value.encode().hex() if mac.value else ""
        if len(mac) > 12:
            mac = mac.replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = MACAddress(mac)
            return mac
        else:
            self.logger.error(f"SNMP MAC address for BEC {self.hostname} failed")
        return None

    def get_telrad_12300_mac_address(self) -> _MACAddress | None:
        try:
            check = self.snmp.walk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "eth0"), None
            )
            mac = self._snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            self.has_snmp = False
            self.logger.error(
                f"SNMP for Telrad 12300 {self.hostname} failed while matching eth0"
            )
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex() if mac.value else ""
        if len(mac) > 12:
            mac = mac.replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = _MACAddress(mac)
            return mac
        return None

    def get_telrad_12000_mac_address(self) -> _MACAddress | None:
        mac = self._snmp_get(".1.3.6.1.4.1.17713.20.2.1.3.13.0")
        if mac is None:
            return None
        if isinstance(mac.value, str) and len(mac.value) > 12:
            mac = _MACAddress(mac.value)
            return mac
        else:
            return None

    def get_wac104_mac_address(self) -> _MACAddress | None:
        try:
            check = self.snmp.walk(".1.3.6.1.2.1.2.2.1.2")
            num = next(
                (val.oid.split(".")[-1] for val in check if val.value == "lan4"), None
            )
            mac = self._snmp_get(f".1.3.6.1.2.1.2.2.1.6.{num}")
        except:
            self.logger.error(
                f"SNMP for WAC104 {self.hostname} failed while matching lan4"
            )
            return None
        if mac is None:
            return None
        mac = mac.value.encode().hex() if mac.value else ""
        if len(mac) > 12:
            mac = mac.replace("c2", "").replace("c3", "")
        if isinstance(mac, str) and len(mac) == 12:
            mac = _MACAddress(mac)
            return mac
        else:
            self.logger.error(
                f"SNMP MAC address for WAC104 {self.hostname} failed (maybe because of c2/c3 removal)"
            )
        return None
