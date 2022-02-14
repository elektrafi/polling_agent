#!/usr/bin/env python3
from raemis import Raemis
from pprint import pprint
from scanner import Scanner


def main():
    scanner = Scanner()
    scanner.run_scan()
    pprint([ue.mac_address() for ue in scanner.raemis_list])


if __name__ == "__main__":
    main()
