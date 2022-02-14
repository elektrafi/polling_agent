#!/usr/bin/env python3
from pprint import pprint
from scanner import Scanner


def main():
    scanner = Scanner()
    scanner.run_scan()
    pprint([ue for ue in scanner.raemis_list])


if __name__ == "__main__":
    main()
