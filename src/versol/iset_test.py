from typing import Iterator

import pytest

from . import iset as mod


def test_empty():
    iv = mod.HalfOpenIntervalSet[int]()
    assert not iv.contains(3)


def test_simple():
    iv = mod.HalfOpenIntervalSet[int]([(3, 91)])
    assert iv.contains(3)
    assert iv.contains(90)
    assert not iv.contains(91)


def test_overlapping_union():
    iv = mod.HalfOpenIntervalSet[int]([(1, 4), (3, 7), (2, 3)])
    assert iv.contains(2)
    assert not iv.contains(7)
    assert iv.contains(1)
    assert iv.contains(3)
    assert iv.contains(4)
    assert iv == mod.HalfOpenIntervalSet[int]([(1, 7)])


def test_disjoint_union():
    iv = mod.HalfOpenIntervalSet[int]([(1, 4), (6, 9)])
    assert iv.contains(1)
    assert not iv.contains(4)
    assert iv.contains(6)
    assert not iv.contains(9)
    assert not iv.contains(5)
    assert iv == mod.HalfOpenIntervalSet[int]([(1, 4), (6, 9)])


def test_intersection():
    iv = mod.HalfOpenIntervalSet[int]([(1, 9)])
    iv2 = mod.HalfOpenIntervalSet[int]([(5, 14)])
    iv = iv.intersection(iv2)
    assert not iv.contains(1)
    assert not iv.contains(2)
    assert not iv.contains(10)
    assert iv.contains(5)
    assert iv == mod.HalfOpenIntervalSet[int]([(5, 9)])


def test_disjoin_intersection():
    iv = mod.HalfOpenIntervalSet[int]([(1, 10)])
    # Intersection with a disjoin interval set is an empty set
    empty = iv.intersection(mod.HalfOpenIntervalSet[int]([(99, 105)]))
    assert empty.empty
    assert empty == mod.HalfOpenIntervalSet[int]()


def test_bad():
    with pytest.raises(mod.InvalidIntervalError):
        mod.HalfOpenIntervalSet([(1, 4), (2, 1)])
    mod.HalfOpenIntervalSet([(1, 4), (3, 7)])


def test_difference():
    iv = mod.HalfOpenIntervalSet[int]([(1, 10)])
    iv2 = mod.HalfOpenIntervalSet[int]([(5, 15)])
    diff = iv.difference(iv2)
    assert diff == mod.HalfOpenIntervalSet[int]([(1, 5)])
    diff2 = iv2 - iv
    assert diff != diff2


def _many_pairs(base: int, n: int, width: int, stride: int) -> Iterator[tuple[int, int]]:
    for x in range(n):
        x = base + x * stride
        yield (x, x + width)


def test_huge():
    pairs = _many_pairs(0, 5000, width=10, stride=30)
    # Generates a huge number of small intervals, but should be reasonably fast
    mod.HalfOpenIntervalSet(pairs)
    mod.HalfOpenIntervalSet([({1: 5}, {31: 4})], key=len)
