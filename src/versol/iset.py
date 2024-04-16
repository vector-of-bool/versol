"""
Defines a half-open interval set type (`HalfOpenIntervalSet`) that can be used
to define and manipulate (non-contiguous) ranges over totally ordered sets.
"""

from __future__ import annotations

import copy
import itertools
from typing import Any, Callable, Generic, Iterable, Iterator, Sequence, TypeVar

from .util import LessThanOrdered, identity, lazygen

PointT = TypeVar("PointT")
"Type variable of totally-ordered types"
_Interval = tuple[PointT, PointT]
"A pair of two values of some point type"
_T = TypeVar("_T")


class InvalidIntervalError(ValueError):
    """
    Exception raised when an interval is mal-formed (e.g. the high point is less than the low point).

    Derived from `ValueError`.
    """


class HalfOpenIntervalSet(Generic[PointT]):
    """
    Defines a set of half-open intervals. Each interval within the set is defined
    by a pair of points of type `PointT`.

    This class is immutable, hashable, and equality-comparable. The set operators
    ``&`` (`.intersection`), ``|`` (`.union`), and ``-`` (`.difference`) are
    defined for this class.

    :param ivs: An iterable of intervals to initialize the set, given as pairs of
        points. The set is formed from the union of the given intervals.
    :param key: A key function to use for comparing points in the range. By
        default, elements are compared directly, which requires that they define
        the ``<`` operator. The return type of the key function must be comparable
        with itself.
    """

    __slots__ = ("__points", "__key")

    # We ignore the error that comes from the default value `identity` function below. This is not
    # fixed by a cast because we want callers to see an error if the point type is not ordered, meaning
    # that they need to provide a key function that maps the points to ordered values
    def __init__(self, ivs: Iterable[_Interval[PointT]] = (), *, key: Callable[[PointT], LessThanOrdered] = identity) -> None:  # type: ignore
        self.__points: list[PointT] = []
        """
        The points that define the interval set.

        Invariants on this list:

        - There is always an even number of points.
        - The points are sorted according to `__less`.
        """
        self.__key = key
        """
        The keying function used for comparing points in the range.
        """
        for iv in ivs:
            # Add each interval we were given. This is where the union operation
            # actually occurs, rather than in the `union()` method.
            self.__union_add(iv)

    @property
    def empty(self) -> bool:
        """`True` if the set is empty, otherwise `False`"""
        return len(self.__points) == 0

    @property
    def intervals(self) -> Iterable[_Interval[PointT]]:
        """
        Obtain an iterable over every sub-interval within the set. Intervals are
        yielded in order from least-to-greatest.

        It is guaranteed that each yielded interval is disjoint.
        """
        # Iter each adjacent pair: [(1, 2), (2, 3), (3, 4), ...]
        pairs = _pairwise(self.__points)
        # An iterable that endlessly yields `True`, `False`, `True`, `False`, ...
        toggles = itertools.cycle((True, False))
        # Yield only every other pair: [(1, 2), <skip>, (3, 4), <skip>, ...]
        return itertools.compress(pairs, toggles)

    def contains(self, p: PointT) -> bool:
        """Returns `True` if the given point is contained by any sub-interval in the interval set"""
        return self.__n_points_before_or_at(p) % 2 == 1

    def __or__(self, other: HalfOpenIntervalSet[PointT]) -> HalfOpenIntervalSet[PointT]:
        """Form the union of the two interval sets. This is an alias of `.union`"""
        return self.union(other)

    def union(self, other: HalfOpenIntervalSet[PointT]) -> HalfOpenIntervalSet[PointT]:
        """
        Form the union of two interval sets. The resulting interval set contains
        every point that is contained by ``self`` and every point contained by ``other``.
        """
        # Generate an iterator over all intervals in both sets:
        both = itertools.chain(self.intervals, other.intervals)
        # Defer to the constuctor, which will perform the union operation
        return HalfOpenIntervalSet(both, key=self.__key)

    def __and__(self, other: HalfOpenIntervalSet[PointT]) -> HalfOpenIntervalSet[PointT]:
        """Form the intersection of two interval sets. This is an alias of `.intersection`"""
        return self.intersection(other)

    def intersection(self, other: HalfOpenIntervalSet[PointT]) -> HalfOpenIntervalSet[PointT]:
        """
        Form the intersection of two interval sets. The resulting interval set will
        contain only the points that are contained by both ``self`` and ``other``.

        If the two interval sets are disjoint (i.e. share no points), then the returned
        interval set will be empty.
        """

        def generate() -> Iterator[_Interval[PointT]]:
            left = _WrappedIterator(iter(self.intervals))
            right = _WrappedIterator(iter(other.intervals))
            while not left.done() and not right.done():
                x = self.__intersect_one_and_adv(left, right)
                if x is not None:
                    yield x

        return HalfOpenIntervalSet(generate(), key=self.__key)

    def __intersect_one_and_adv(
        self,
        left: _WrappedIterator[_Interval[PointT]],
        right: _WrappedIterator[_Interval[PointT]],
    ) -> _Interval[PointT] | None:
        """
        Return the single interval intersection of two intervals given by the
        operand iterators, and advance the iterator that is used to form that
        intersection. Returns `None` if there is no intersection, and advances
        the lesser of the two ranges
        """
        l_lo, l_hi = left.current()
        r_lo, r_hi = right.current()
        if self.__less(r_lo, l_lo):
            # The base of the right-hand interval is less-than the base of the left-hand interval.
            # The intersection is commutative. Swap the two operands and perform the intersection.
            return self.__intersect_one_and_adv(right, left)
        if not self.__less(r_lo, l_hi):
            # The base of the right-hand operand is greater than the top of the left-hand set, so
            # they have no overlap. Discard the left-hand interval.
            left.advance()
            return None  # No intersection between these to intervals
        if not self.__less(l_hi, r_hi):
            # The left-hand interval completely encloses the right-hand interval,
            # so we can just return the right hand interval as the intersection.
            right.advance()
            return (r_lo, r_hi)
        # The two intervals overlap, but neither contains the other. Return
        # the intersection and advance the left-hand iterator
        assert self.__less(l_hi, r_hi)
        left.advance()
        return (r_lo, l_hi)

    def __union_add(self, iv: _Interval[PointT]) -> None:
        """
        Insert the given interval into the set such that all points in the current
        set and all points in the given interval will now be in the set.

        This function mutates the interval set. It is only used by ``__init__``
        to initialize the set.
        """
        lo, hi = iv
        # Check that the given points are properly ordered. This is the only place
        # that this check is performed (this function is invoked by __init__)
        if self.__less(hi, lo):
            raise InvalidIntervalError(f"Interval is not valid (low={lo!r}, high={hi!r})")
        left = self.__n_points_before_or_at(lo)
        starts_within = left % 2 == 1
        right = self.__n_points_before(hi)
        ends_within = right % 2 == 1
        if starts_within:
            if ends_within:
                self.__points[left:right] = ()
            else:
                self.__points[left:right] = (hi,)
        elif ends_within:
            self.__points[left:right] = (lo,)
        else:
            self.__points[left:right] = (lo, hi)

    def __sub__(self, other: HalfOpenIntervalSet[PointT]) -> HalfOpenIntervalSet[PointT]:
        """
        Obtain the different between two sets. This function is a convenience
        alias of `.difference`.
        """
        return self.difference(other)

    def difference(self, other: HalfOpenIntervalSet[PointT]) -> HalfOpenIntervalSet[PointT]:
        """
        Obtain the difference between two interval sets. The difference set contains
        all points from ``self`` that are not also contained within ``other``. The
        following set-operation properties apply:

        - If ``self`` and ``other`` are disjoin, returns ``self``.
        - If ``other`` entirely contains ``self``, returns an empty set.
        - Otherwise, returns a new set that is unequal both to ``self`` and to ``other``
        """
        dup = copy.copy(self)
        for iv in other.intervals:
            dup.__remove(iv)
        return dup

    def __remove(self, iv: _Interval[PointT]) -> None:
        """
        Remove all points within ``iv`` from the set. This function is only used
        for calculating `.difference()`.
        """
        low, high = iv
        left = self.__n_points_before_or_at(low)
        right = self.__n_points_before(high)
        if left % 2:  # Starts within the set?
            if right % 2:  # Ends within the set?
                self.__points[left:right] = (low, high)
            else:
                self.__points[left:right] = (low,)
        elif right % 2:  # Ends within the set?
            self.__points[left:right] = (high,)
        else:
            self.__points[left:right] = ()

    def __repr__(self) -> str:
        pairs = (f"[{lo!r}, {hi!r})" for lo, hi in self.intervals)
        return f'<HalfOpenIntervalSet ⟨{", ".join(pairs)}⟩>'

    def __eq__(self, other: object) -> bool:
        """
        Compare two sets for equality. The two sets are equivalent if it is
        defined by the same boundary points and the sets use the same key
        function.

        This will compare the point objects using the default ``==`` operator.
        """
        if not isinstance(other, HalfOpenIntervalSet):
            return NotImplemented
        return self.__key == other.__key and self.__points == other.__points  # type: ignore

    def __hash__(self) -> int:
        return hash(tuple(self.intervals)) ^ hash(self.__key)

    def __n_points_before(self, p: PointT) -> int:
        "Get the number of points that are less-than the point `p`"
        return _partition_point(self.__points, lambda mine: self.__less(mine, p))

    def __n_points_before_or_at(self, p: PointT) -> int:
        "Get the number of points that are less-than-or-equal-to the point `p`"
        return _partition_point(self.__points, lambda mine: not self.__less(p, mine))

    def __less(self, x: PointT, y: PointT) -> bool:
        """
        Return `True` if point ``x`` is less-than point ``y``, using the key function
        that was defined for this set
        """
        return self.__key(x) < self.__key(y)


def _partition_point(xs: Sequence[_T], predicate: Callable[[_T], bool]) -> int:
    """
    Return the index of the first element in ``xs`` for which ``predicate`` returns `False`,
    with the precondition that ``xs`` is partitioned according to ``predicate``.
    """
    # Implement a binary search over the sequence
    length = len(xs)
    if length == 1:
        # Base case
        return 1 if predicate(xs[0]) else 0
    mid = length // 2
    if mid == length:
        # We are at the end of the range so this must be the partition point
        # (This will be hit immediately if the range is empty)
        return mid
    if predicate(xs[mid]):
        # The midpoint is within the partition. Check the later half:
        return mid + _partition_point(xs[mid:], predicate)
    else:
        # The midpoint is outside of the partition. Check the first half:
        return _partition_point(xs[:mid], predicate)


def _pairwise(its: Iterable[_T]) -> Iterable[tuple[_T, _T]]:
    """Implements `itertools.pairwise`."""
    if hasattr(itertools, "pairwise"):
        # Defer to itertools' implementation of pairwise, which is likely more optimal
        return itertools.pairwise(its)  # type: ignore
    return _pairwise_gen(its)


@lazygen
def _pairwise_gen(its: Iterable[_T]) -> Iterator[tuple[_T, _T]]:
    "Implement `itertools.pairwise` as a generator function"
    it = iter(its)
    try:
        a = next(it)
        b = next(it)
        while True:
            yield a, b
            a = b
            b = next(it)

    except StopIteration:
        pass


_DONE_SENTINEL: Any = object()
"Signal to _WrappedIterator when an iterator finishes"


class _WrappedIterator(Generic[_T]):
    """
    Wrap an iterator as a mutable object that stores the iterator's result and
    allows advancing it.
    """

    def __init__(self, it: Iterator[_T]) -> None:
        self.__iter = it
        "The wrapped iterator"
        self.__value: _T = next(it, _DONE_SENTINEL)
        "The currently-held iterator value"

    def done(self) -> bool:
        """Yield `True` if the iterator is finished"""
        return self.__value is _DONE_SENTINEL

    def current(self) -> _T:
        """Obtain the currently-held value from the iterator."""
        assert not self.done(), "Attempted to access the value of a completed iterator"
        return self.__value

    def advance(self) -> None:
        """Advance the iterator to the next element."""
        assert not self.done(), "Attempted to advance finished iterator"
        self.__value = next(self.__iter, _DONE_SENTINEL)

    def __repr__(self) -> str:
        if self.done():
            return "<_WrappedIterator (done)>"
        return f"<_WrappedIterator current={self.current!r}>"
