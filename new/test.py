#!/usr/bin/env python3

from types import new_class


class test(object):
    def __init__(self, data):
        self.__dict__.update(data)


def create_deep_object(name: str, data: dict) -> type:
    cls = new_class(name)()
    for k in data.keys():
        if isinstance(data[k], dict):
            obj = create_deep_object(k, data[k])
        else:
            obj = data[k]
        cls.__dict__[k] = obj
    return cls


import pprint


def fn(acct: AccountType):
    if acct is None:
        return
    id = acct["id"]
    name = acct["name"]
    addresses = acct["addresses"]["entities"]
    if len(addresses) < 1:
        return
    address = addresses[0]
    ue = self.__get_ue_by_client_name(name)
    if ue is None:
        return
    if ue.client is None:
        ue.client = Client(name)
    if ue.client.address is None:
        ue.client.address = Address()

    ue.client.sonar_id = id
    ue.client.address.sonar_id = address["id"]
    ue.client.address.line1 = address["line1"]
    ue.client.address.line2 = address["line2"]
    ue.client.address.city = address["city"]
    ue.client.address.zip_code = address["zip"]
