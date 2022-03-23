#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Iterable, Mapping, Any, ParamSpec, TypeVar, Iterator


P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", list[Future], Future)
FList = type(list[Future[Any]])
TPE = type(ThreadPoolExecutor)


class Pipeline:
    mainExec: ThreadPoolExecutor
    __executors: set[ThreadPoolExecutor]
    cursor: Future

    def __init__(self, pool_size: int = 175):
        self.mainExec = ThreadPoolExecutor(max_workers=pool_size)
        self.__executors = {self.mainExec}
        self.cursor = Future()

    def __del__(self):
        (x.shutdown(wait=True, cancel_futures=False) for x in self.__executors)

    def map(
        self,
        fn: Callable[P, T],
        iterable: Iterable[Any] | Any,
        timeout: float | None = None,
        chunksize: int = -1,
    ) -> Iterator[T]:
        return self.mainExec.map(fn, iterable, timeout=timeout, chunksize=chunksize)

    def start_fn_in_executor(
        self,
        e: TPE,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        self.__executors.add(e)
        self.cursor = e.submit(fn, *args, **kwargs)
        return self.cursor

    def start_fn(
        self,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        self.cursor = self.start_fn_in_executor(self.mainExec, fn, *args, **kwargs)
        return self.cursor

    def start_fn_after_cursor(
        self,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
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
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        def call_fn_after_future(
            f: Future[Any],
            fn: Callable[P, T],
            *args: Iterable[Any] | Any,
            **kwargs: Mapping[str, Any],
        ) -> T:
            while not f.done():
                pass
            return fn(*args, **kwargs)

        self.cursor = self.mainExec.submit(call_fn_after_future, f, fn, *args, **kwargs)
        return self.cursor

    def start_fn_after_futures_list(
        self,
        l: FList,
        fn: Callable[P, T],
        *args: Iterable[Any] | Any,
        **kwargs: Mapping[str, Any],
    ) -> Future[T]:
        f = self.merge_futures_list(l)
        self.cursor = self.start_fn_after_future(f, fn, *args, **kwargs)
        return self.cursor

    def merge_futures_list(self, l: FList) -> FList:
        def merge(l: FList) -> list[Any]:
            while not self.__all_futures_done(l):
                pass
            return [x.result() for x in l]

        return self.mainExec.submit(merge, l)

    def __all_futures_done(self, futures: FList) -> bool:
        return all(x.done() for x in futures)
