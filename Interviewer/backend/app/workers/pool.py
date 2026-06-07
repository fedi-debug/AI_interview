"""Simple thread pool for CPU-bound AV workers (keeps FastAPI handlers light)."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable, TypeVar

T = TypeVar("T")

_pool: ThreadPoolExecutor | None = None


def get_worker_pool(max_workers: int = 4) -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="hirenest")
    return _pool


async def run_in_worker(fn: Callable[..., T], *args, **kwargs) -> T:
    loop = asyncio.get_event_loop()
    pool = get_worker_pool()
    return await loop.run_in_executor(pool, partial(fn, *args, **kwargs))
