#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from json import load
from typing import Any, Iterator, Type
import os
from typing_extensions import Self

from attr import attributes


class Config:

    def __new__(cls, vals: dict[str, Any]) -> Self:
        obj = super().__new__(cls)
        for key in vals:
            setattr(obj, key, vals[key])
        return obj

    def __setattr__(self, name: str, val: Any) -> None:
        if isinstance(val, dict):
            super().__setattr__(name, Config(val))
        else:
            super().__setattr__(name, val)

    def __getattribute__(self, __name: str) -> Any:
        return super().__getattribute__(__name)


class Application:
    _config = None

    @classmethod
    @property
    def config(cls) -> Config:
        def env_var_names(config: Config) -> Iterator[str]:
            if vars(config) is None: return []
            for name in vars(config):
                if isinstance(getattr(config, name), Config):
                    subs = env_var_names(getattr(config, name))
                    for sub in subs:
                        yield f'{name.upper()}_{sub.upper()}'
                else:
                    yield name

        def set_env_var(obj: Config, name: str, val: Any):
            parts = name.lower().split('_')
            if len(parts) == 1:
                setattr(obj, name, val)
            elif len(parts) > 1:
                set_env_var(getattr(obj, parts[0]), '_'.join(parts[1:]), val)

        if cls._config is None:
            with open('config.json', 'r') as conf:
                json = load(conf)
                cls._config = Config(json)
            for name in env_var_names(cls._config):
                var = os.environ.get(name)
                if var:
                    set_env_var(cls._config, name, var)
        return cls._config


if __name__ == '__main__':
    print(Application.config.sonar.key, Application.config.sonar.url)
