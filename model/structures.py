#!/usr/bin/env python3
# Copyright 2021 Brenden Smith
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import logging as _logging
from typing import Any as _Any, Iterable as _Iterable, TypeVar as _TypeVar
from .atoms import Item as _Item, Account as _Account


_T = _TypeVar("_T", _Item, _Account)


class MergeSet(set[_T]):
    _log = _logging.getLogger(__name__)

    def add(self, __element: _T) -> _T:
        try:
            if __element == _Item():
                return __element
            self._log.info(f"adding old {__element} to set")
            mine = next(x for x in iter(self) if x == __element)
        except StopIteration:
            self._log.debug(
                f"merged key of {__element} not found in the set, adding it"
            )
            self._log.info(f"adding new {__element} to set")
            super().add(__element)
            return __element
        try:
            super().remove(mine)
        except KeyError as ke:
            self._log.exception(
                f"somehow errored removing {mine} from set after finding it in the set"
            )
        current = __element
        while True:
            items = current.__dict__.items()
            self._log.debug(f"adding all items {items} to {mine}")
            for k, v in items:
                try:
                    setattr(mine, k, v)
                    self._log.debug(f"added {v} for {k}")
                except:
                    self._log.exception(
                        f"error when adding {v} for key {k} to {mine}", stack_info=True
                    )
                    continue
            try:
                current = next(x for x in iter(self) if x == mine)
                super().remove(current)
            except KeyError as ke:
                self._log.exception(
                    f"somehow errored removing {current} from set after finding it in the set"
                )
                raise ke
            except StopIteration:
                break
        self._log.debug(f"adding the updated item back, maybe new items in key: {mine}")
        self._log.info(f"adding new {mine} to set")
        super().add(mine)
        return mine

    def issubset(self, __s: _Iterable[_Any]) -> bool:
        return all(map(lambda x: x in iter(self), __s))

    def __contains__(self, __o: object) -> bool:
        if not isinstance(__o, _Item | _Account):
            raise ValueError("must be Item type to test inclusion")
        return any(map(lambda x: x == __o, iter(self)))

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, MergeSet):
            return False
        return self.issubset(__o) and __o.issubset(self)
