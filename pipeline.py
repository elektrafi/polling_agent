#!/usr/bin/env python3

from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import (
    Callable,
    Iterable,
    Mapping,
    Any,
    ParamSpec,
    TypeVar,
    Iterator,
)
import logging
from typing_extensions import Self


P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", list[Future], Future)
FList = type(list[Future[Any]])


class Pipeline:
    procExec: ProcessPoolExecutor
    threadExec: ThreadPoolExecutor
    cursor: Future
    logger = logging.getLogger(__name__)
    _inst: Self | None = None

    def __init__(self, pool_size: int = 250):
        self.procExec = ProcessPoolExecutor(max_workers=8)
        self.threadExec = ThreadPoolExecutor(max_workers=pool_size)
        self.cursor = Future()

    def __new__(cls: type[Self], *args, **kwargs) -> Self:
        if not cls._inst:
            cls._inst = super(Pipeline, cls).__new__(cls)
        return cls._inst

    def __del__(self):
        (
            x.shutdown(wait=True, cancel_futures=False)
            for x in [self.procExec, self.threadExec]
        )

    def map(
        self,
        fn: Callable[P, T],
        iterable: Iterable[Any] | Any,
        timeout: float | None = None,
<<<<<<< Updated upstream
        chunksize: int = -1,
=======
        chunksize: int = 200,
>>>>>>> Stashed changes
    ) -> Iterator[T]:

        return self.procExec.map(fn, iterable, timeout=timeout, chunksize=chunksize)

    def map_in_executor(
        self,
        e: ProcessPoolExecutor,
        fn: Callable[P, T],
        iterable: Iterable[Any] | Any,
        timeout: float | None = None,
        chunksize: int = 1,
    ) -> Iterator[T]:

<<<<<<< Updated upstream
=======
        return e.map(fn, iterable, timeout=timeout, chunksize=chunksize)

>>>>>>> Stashed changes
    def start_fn_in_executor(
        self,
        e: ProcessPoolExecutor | ThreadPoolExecutor,
        fn: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Future[T]:
<<<<<<< Updated upstream
        self.__executors.add(e)
        self.cursor = e.submit(fn, *args, **kwargs)
=======
        if e == self.threadExec:
            self.cursor = e.submit(fn, *args, **kwargs)
>>>>>>> Stashed changes
        return self.cursor

    def start_fn(
        self,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        self.cursor = self.start_fn_in_executor(self.threadExec, fn, *args, **kwargs)
        return self.cursor

    def start_fn_after_cursor(
        self,
        fn: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Future[T]:
        self.cursor = self.start_fn_after_future(self.cursor, fn, *args, **kwargs)
        return self.cursor

    def start_fns_after_future(
        self,
        f: Future[Any],
        fns: list[Callable[P, T]],
        alist: list[Iterable[Any] | Any] = [],
        kwalist: list[Mapping[str, Any]] = [],
    ) -> Future[T]:
        if not alist:
            for _ in range(len(fns)):
                alist.append(())
        if not kwalist:
            for _ in range(len(fns)):
                kwalist.append({})
        ret = []
        for i, fn in enumerate(fns):
            ret.append(self.start_fn_after_future(f, fn, *alist[i], **kwalist[i]))
        self.cursor = self.merge_futures_list(ret)
        return self.cursor

    def start_fn_after_future(
        self,
        f: Future[Any],
        fn: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Future[T]:
        def call_fn_after_future(
            f: Future[Any],
            fn: Callable[P, T],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> T:
            while not f.done():
                pass
            return fn(*args, **kwargs)

        self.cursor = self.threadExec.submit(
            call_fn_after_future, f, fn, *args, **kwargs
        )
        return self.cursor

    def start_fn_after_futures_list(
        self,
        l: FList,
        fn: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Future[T]:
        f = self.merge_futures_list(l)
        self.cursor = self.start_fn_after_future(f, fn, *args, **kwargs)
        return self.cursor

    def merge_futures_list(self, l: FList) -> FList:
        def merge(l: FList) -> list[Any]:
            while not self.__all_futures_done(l):
                pass
            return [x.result() for x in l]

        return self.threadExec.submit(merge, l)

    def __all_futures_done(self, futures: FList) -> bool:
        return all(x.done() for x in futures)
