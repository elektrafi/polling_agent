#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.


import pytest
from model.network import IPv4Address, MACAddress, IMEI, IMSI


class TestIMSI:
    @pytest.fixture
    def imsi_one(self):
        yield IMSI("123456789012345")

    @pytest.fixture
    def imsi_two(self):
        yield IMSI("123456789012345")

    @pytest.fixture
    def imsi_three(self):
        yield IMSI("123456789012346")

    def test_create(self, imsi_one, imsi_two):
        assert imsi_one
        assert imsi_two

    def test_eq(self, imsi_one, imsi_two):
        assert imsi_one == imsi_two

    def test_neq(self, imsi_one, imsi_three):
        assert imsi_one != imsi_three

    def test_hash(self, imsi_one, imsi_two):
        assert hash(imsi_one) == hash(imsi_two)

    def test_len(self):
        with pytest.raises(ValueError):
            IMSI("1234567890123456")

    def test_letter(self):
        with pytest.raises(ValueError):
            IMSI("12345678901234a")


class TestIMEI:
    @pytest.fixture
    def imei_one(self):
        yield IMEI("123456789012345")

    @pytest.fixture
    def imei_two(self):
        yield IMEI("123456789012345")

    @pytest.fixture
    def imei_three(self):
        yield IMEI("1234567890123456")

    def test_create(self, imei_one, imei_two):
        assert imei_one
        assert imei_two

    def test_eq(self, imei_one, imei_two):
        assert imei_one == imei_two

    def test_neq(self, imei_one, imei_three):
        assert imei_one != imei_three

    def test_hash(self, imei_one, imei_two):
        assert hash(imei_one) == hash(imei_two)

    def test_len(self):
        with pytest.raises(ValueError):
            IMEI("12345678901234567")

    def test_letter(self):
        with pytest.raises(ValueError):
            IMEI("12345678901234a")


class TestMACAddress:
    @pytest.fixture
    def address_one(self):
        yield MACAddress("1234567890ab")

    @pytest.fixture
    def address_two(self):
        yield MACAddress("12:34:56:78:90:AB")

    @pytest.fixture
    def address_three(self):
        yield MACAddress("12:34:56:78:90:Cd")

    def test_create(self, address_one):
        assert address_one

    def test_eq(self, address_one, address_two):
        assert address_one == address_two

    def test_neq(self, address_one, address_two, address_three):
        assert address_one != address_three and address_two != address_three

    def test_str(self, address_one):
        assert str(address_one) == "12:34:56:78:90:AB"

    def test_hash(self, address_one, address_two):
        assert hash(address_one) == hash(address_two)


class TestIPAddress:
    @pytest.fixture
    def address_one(self):
        yield IPv4Address(address="192.68.1.100")

    @pytest.fixture
    def address_one_dup(self):
        yield IPv4Address(address="192.68.1.100", netmask=(255, 255, 255, 255))

    @pytest.fixture
    def address_two(self):
        yield IPv4Address(address="192.68.1.99", netmask=(255, 255, 255, 0))

    @pytest.fixture
    def address_in_network(self):
        yield IPv4Address(address="192.68.1.100", cidr_mask=24)

    @pytest.fixture
    def address_cidr_c(self):
        yield IPv4Address(address="192.68.1.99", cidr_mask=24)

    @pytest.fixture
    def network_c(self):
        yield (192, 68, 1, 0)

    @pytest.fixture
    def broadcast_c(self):
        yield (192, 68, 1, 255)

    def test_create(self, address_one):
        assert address_one

    def test_eq(self, address_one, address_one_dup):
        assert address_one == address_one_dup

    def test_hash(self, address_one, address_one_dup):
        assert hash(address_one) == hash(address_one_dup)

    def test_eq_netmask(self, address_two, address_cidr_c):
        assert address_two == address_cidr_c

    def test_neq(self, address_one, address_two):
        assert address_one != address_two

    def test_neq_diff_netmask(self, address_one, address_in_network):
        assert address_one != address_in_network

    def test_neq_netmask(self, address_two, address_in_network):
        assert address_two != address_in_network

    def test_network_prop(self, address_cidr_c, network_c):
        assert address_cidr_c.network == network_c

    def test_broadcast_prop(self, address_cidr_c, broadcast_c):
        assert address_cidr_c.broadcast == broadcast_c

    def test_contains(self, address_two, address_in_network):
        assert address_in_network in address_two

    def test_not_contains(self, address_one, address_in_network):
        assert address_one not in address_in_network

    def test_str(self, address_two):
        assert str(address_two) == "192.68.1.99/24"
