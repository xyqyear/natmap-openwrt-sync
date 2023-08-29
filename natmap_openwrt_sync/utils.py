import asyncio
from typing import Awaitable, Callable, ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


def aioify(func: Callable[P, T]) -> Callable[P, Awaitable[T]]:
    """
    make a function async with loop.run_in_executor
    """

    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper
