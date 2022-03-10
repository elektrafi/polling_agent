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
