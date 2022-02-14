#!/usr/bin/env python3
import telnetlib as tn
from time import sleep


class TelnetClient:
    def __init__(self, host, port=23, user="admin", passwd="EFI_Buna2020"):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.port = port

    def cmd(self, cmd: str) -> str:
        with tn.Telnet(self.host, port=self.port, timeout=5) as client:
            client.read_until(b"login: ")
            client.write(self.user.encode("ascii") + b"\n")
            client.read_until(b"Password: ")
            client.write(self.passwd.encode("ascii") + b"\n")
            sleep(0.25)
            client.write(cmd.encode("ascii") + b"\n")
            sleep(0.25)
            ret = client.read_all().decode("ascii")
            client.write(b"exit\n")
        return ret
