#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import pytest
from model.structures import MergeSet
from model.network import MACAddress, IMEI, IMSI
from model.atoms import Item


class TestMergeSet:
    @pytest.fixture
    def sonar_id(self):
        yield "1234"

    @pytest.fixture
    def mac_address(self):
        yield MACAddress("abcdef123456")

    @pytest.fixture
    def mac_address_dup(self):
        yield MACAddress("AB:CD:EF:12:34:56")

    @pytest.fixture
    def mac_address2(self):
        yield MACAddress("1234567890ab")

    @pytest.fixture
    def imei(self):
        yield IMEI("1" * 15)

    @pytest.fixture
    def imei2(self):
        yield IMEI("12" * 8)

    @pytest.fixture
    def imsi(self):
        yield IMSI("1" * 15)

    @pytest.fixture
    def empty_set(self):
        yield MergeSet()

    @pytest.fixture
    def empty_item(self):
        yield Item()

    @pytest.fixture
    def item_id(self, sonar_id):
        empty_item = Item()
        empty_item.sonar_id = sonar_id
        yield empty_item

    @pytest.fixture
    def item_mac1(self, mac_address):
        empty_item = Item()
        empty_item.mac_address = mac_address
        yield empty_item

    @pytest.fixture
    def item_id_mac1_dup(self, sonar_id, mac_address_dup):
        empty_item = Item()
        empty_item.sonar_id = sonar_id
        empty_item.mac_address = mac_address_dup
        yield empty_item

    @pytest.fixture
    def set_id_mac1_dup(self, empty_set, item_id_mac1_dup):
        empty_set.add(item_id_mac1_dup)
        yield empty_set

    @pytest.fixture
    def set_id(self, empty_set, item_id):
        empty_set.add(item_id)
        yield empty_set

    @pytest.fixture
    def set_all(self, empty_set, sonar_id, mac_address2, imei, imsi):
        i = Item()
        i.sonar_id = sonar_id
        i.mac_address = mac_address2
        i.imei = imei
        i.imsi = imsi
        empty_set.add(i)
        yield empty_set

    def test_update(self, set_id_mac1_dup, item_id, item_mac1):
        t = MergeSet()
        t.add(item_id)
        t.add(item_mac1)
        assert set_id_mac1_dup == t

    def test_neq(self, item_id, set_id_mac1_dup):
        t = MergeSet()
        t.add(item_id)
        assert t != set_id_mac1_dup

    def test_set_update(self, set_id_mac1_dup, item_id, mac_address):
        t = MergeSet()
        t.add(item_id)
        i = Item()
        i.mac_address = mac_address
        t.add(i)
        assert t == set_id_mac1_dup

    def test_empty(self, empty_item):
        t = MergeSet()
        t.add(empty_item)
        assert t

    def test_none_item(self, imei):
        empty_set = MergeSet()
        i = Item()
        empty_set.add(i)
        i = Item()
        i.imei = imei
        empty_set.add(i)
        assert empty_set

    def test_none_neq(self, empty_item, imsi):
        t1 = MergeSet()
        t2 = MergeSet()
        t1.add(empty_item)
        i = Item()
        i.imsi = imsi
        t2.add(i)
        assert t1 != t2

    def test_all(self, empty_item, set_all, sonar_id, mac_address2, imei, imsi):
        t = MergeSet()
        empty_item.sonar_id = sonar_id
        empty_item.mac_address = mac_address2
        empty_item.imei = imei
        empty_item.imsi = imsi
        t.add(empty_item)
        assert t == set_all

    def test_cascade_merge(self, set_all, imei, imsi, mac_address, sonar_id):
        i1 = Item()
        i2 = Item()
        i3 = Item()
        i1.sonar_id = sonar_id
        i1.mac_address = mac_address
        i2.imsi = imsi
        i2.imei = imei
        i3.imei = imei
        i3.mac_address = mac_address
        t = MergeSet()
        t.add(i1)
        t.add(i2)
        t.add(i3)
        assert t == set_all
