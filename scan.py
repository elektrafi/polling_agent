#!/usr/bin/env python3
from raemis import Raemis
from pprint import pprint
from scanner import Scanner


def main():
    scanner = Scanner()
    pprint(scanner.snmp_list)


if __name__ == "__main__":
    main()
