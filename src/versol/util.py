import functools
from typing import Any, Callable, Generic, Iterable, Iterator, Protocol, TypeVar, cast, overload

from typing_extensions import ParamSpec, Self


T = TypeVar("T")
"""Generic invariant unbounded type parameter"""
Ps = ParamSpec("Ps")
"""Generic parameter spec type parameter"""


def lazygen(fn: Callable[Ps, Iterator[T]]) -> Callable[Ps, Iterable[T]]:
    """
    Annotate a function that returns an iterator to become a function that returns
    an iterable. The underlying function is only called when the ``__iter__`` is
    called on the returned iterable.

    This allows functions returning iterators (such as generators) to be iterated
    repeatedly, and they always "start from the beginning" when iterated.
    """

    @functools.wraps(fn)
    def _wrapped(*args: Ps.args, **kwargs: Ps.kwargs) -> Iterable[T]:
        return _LazyGen(fn, *args, **kwargs)

    return _wrapped


class _LazyGen(Generic[T, Ps]):
    def __init__(self, __fn: Callable[Ps, Iterator[T]], /, *args: Ps.args, **kwargs: Ps.kwargs):
        self._fn = __fn
        self._args = args
        self._kwargs = kwargs

    def __iter__(self) -> Iterator[T]:
        return self._fn(*self._args, **self._kwargs)


class LessThanOrdered(Protocol):
    """Match types which have a defined operator `<` returning `bool`."""

    def __lt__(self, other: Self, /) -> bool: ...


def identity(x: T) -> T:
    """
    A function which simply returns the argument that was given.
    """
    return x


_OrderedT = TypeVar("_OrderedT", bound=LessThanOrdered)
"Type variable that matches ordered types"


@overload
def minmax(left: _OrderedT, right: _OrderedT, /) -> tuple[_OrderedT, _OrderedT]: ...


@overload
def minmax(left: T, right: T, /, *, key: Callable[[T], LessThanOrdered]) -> tuple[T, T]: ...


def minmax(left: T, right: T, /, *, key: Callable[[T], LessThanOrdered] = cast(Any, identity)) -> tuple[Any, Any]:
    """
    Compare two objects and return a pair where the lesser of the parameters is
    the first element, and the greater element is the second element. If neither
    object compares less than the other, returns ``(left, right)``,

    :param left: An object to compare
    :param right: An object to compare:
    :param key: If given, a key function that maps the two objects to a new value
        that is used for the comparison.
    """
    lk = key(left)
    rk = key(right)
    if lk < rk:
        return left, right
    elif rk < lk:
        return right, left
    else:
        return left, right
