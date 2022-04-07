#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from functools import partial
from typing import Mapping
from types import new_class


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
