#!/usr/bin/env python3

from functools import partial
from typing import Mapping
from types import new_class


# class metaDevice(type):
#    def __init__(self, *args, **kwargs):
#        super().__init__(self, *args, **kwargs)
#
#    def __new__(cls, *args, **kwargs):
#        super().__new__(cls, *args, **kwargs)
#
#    def __getattribute__(self, __name: str) -> Any:
#        attr = super().__getattribute__(__name)
#        if not attr:
#            d = sorted(list(super().__dict__.keys()))
#            pos = bisect(d, __name)
#            if pos >= len(d):
#                return super().__getattribute__(d[-1])
#            if pos <= 0:
#                return super().__getattribute__(d[0])
#            low, high = d[pos - 1], d[pos]
#            i = 0
#            ret = None
#            while True:
#                if i >= len(low):
#                    ret = high
#                    break
#                elif i >= len(high):
#                    ret = low
#                    break
#                ret = (
#                    low
#                    if abs(ord(low[i]) - ord(__name[i]))
#                    < abs(ord(high[i]) - ord(__name[i]))
#                    else high
#                )
#                if low[i] != high[i]:
#                    break
#                i += 1
#            attr = ret
#        return super().__getattribute__(attr)


def create_deep_object(name: str, data: dict | str | list) -> object:
    if isinstance(data, Mapping):
        cls = new_class(name)()
        keys = data.keys()
        if "_value" in keys and "_type" in data and "_object" in data:
            return data["_value"]
        for k in keys:
            prefix = ""
            if k[0].isnumeric():
                prefix = "item"
            cls.__dict__[f"{prefix}{k}"] = create_deep_object(k, data[k])
        return cls
    return data


device_object_hook = partial(create_deep_object, "Device")
