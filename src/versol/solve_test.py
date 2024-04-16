from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pytest

from . import solve as mod
from .report import ConsoleLogger, generate_report


@dataclass(frozen=True, unsafe_hash=True, order=True)
class dep:

    name: str
    versions: frozenset[int]

    def __repr__(self) -> str:
        if len(self.versions) == 1:
            return f"<dep {self.name}@{next(iter(self.versions))}>"
        else:
            return f"<dep {self.name}@{set(self.versions)}>"

    @property
    def key(self) -> str:
        return self.name

    def implied_by(self, o: dep) -> bool:
        return self.name == o.name and self.versions.issuperset(o.versions)

    def intersection(self, o: dep) -> dep:
        return dep(self.name, self.versions & o.versions)

    def union(self, o: dep) -> dep:
        return dep(self.name, self.versions | o.versions)

    def difference(self, o: dep) -> dep:
        return dep(self.name, self.versions - o.versions)

    @property
    def intrinsically_unsatisfiable(self) -> bool:
        return not len(self.versions)


@dataclass(frozen=True, unsafe_hash=True, order=True)
class pkg:

    name: str
    version: int
    deps: tuple[dep, ...]


@dataclass(frozen=True)
class repo:

    pkgs: set[pkg]

    def best_candidate(self, d: dep) -> tuple[dep, Iterable[dep]] | None:
        with_name = (p for p in self.pkgs if p.name == d.name)
        matching_version = sorted(p for p in with_name if p.version in d.versions)
        p = next(iter(matching_version), None)
        if p is None:
            return None
        return dep(p.name, frozenset({p.version})), p.deps


def test_simple_solve():
    r = repo({pkg("foo", 2, ())})
    r = list(mod.solve([dep("foo", frozenset({1, 2}))], r))
    assert r == [dep("foo", frozenset({2}))]


def test_empty():
    r = repo(set())
    res = list(mod.solve([], r))
    assert res == []


def test_simple_multicand():
    r = repo(
        {
            pkg("foo", 1, ()),
            pkg("foo", 2, ()),
            pkg("foo", 3, ()),
            pkg("foo", 4, ()),
        }
    )
    res = list(mod.solve([dep("foo", frozenset({7, 99, 2}))], r))
    assert res == [dep("foo", frozenset({2}))]


def test_simple_transitive():
    r = repo(
        {
            pkg("foo", 1, (dep("bar", frozenset({3, 4})),)),
            pkg("bar", 3, ()),
        }
    )
    sln = list(mod.solve([dep("foo", frozenset({1}))], r))
    sln.sort()
    assert sln == [dep("bar", frozenset({3})), dep("foo", frozenset({1}))]


def test_multiple_transitive_requirements():
    r = repo(
        {
            pkg("foo", 1, (dep("bar", frozenset((3, 4, 5, 6))), dep("baz", frozenset((5, 6, 7))))),
            pkg("bar", 5, ()),
            pkg("baz", 7, ()),
        }
    )
    sln = sorted(mod.solve([dep("foo", frozenset([1]))], r))
    assert sln == [dep("bar", frozenset([5])), dep("baz", frozenset([7])), dep("foo", frozenset([1]))]


def test_simple_backtrack():
    r = repo(
        {
            pkg("foo", 1, (dep("bar", frozenset((1, 2, 3, 4, 5, 6))), dep("baz", frozenset((3, 4, 5, 6, 7, 8))))),
            pkg("bar", 0, ()),
            pkg("bar", 1, ()),
            pkg("bar", 2, ()),
            pkg("bar", 3, ()),
            pkg("bar", 4, ()),
            pkg("baz", 6, (dep("bar", frozenset((4, 5))),)),
        }
    )
    sln = sorted(mod.solve([dep("foo", frozenset((1, 2)))], r))
    assert sln == [dep("bar", frozenset({4})), dep("baz", frozenset({6})), dep("foo", frozenset({1}))]


_BareReq = tuple[str, Iterable[int]]
_BarePkg = tuple[str, int, Iterable[_BareReq]]


@dataclass(frozen=True)
class Case:
    """
    Case
    """

    name: str
    packages: Iterable[_BarePkg]
    requirements: Iterable[_BareReq]
    expected: Iterable[tuple[str, int]] | None


_CASES: list[Case] = [
    Case("Empty", (), (), ()),
    Case(
        "Simple interdependencies",
        [
            ("a", 1, [("aa", [1, 2]), ("ab", [1, 2])]),
            ("b", 1, [("ba", [1, 2]), ("bb", [1, 2])]),
            ("aa", 1, []),
            ("ab", 1, []),
            ("ba", 1, []),
            ("bb", 1, []),
        ],
        [("a", [1, 2]), ("b", [1, 2])],
        [
            ("a", 1),
            ("b", 1),
            ("aa", 1),
            ("ab", 1),
            ("ba", 1),
            ("bb", 1),
        ],
    ),
    Case(
        "Simple overlapping",
        [
            ("a", 1, [("shared", range(200, 400))]),
            ("b", 1, [("shared", range(300, 500))]),
            ("shared", 200, []),
            ("shared", 299, []),
            ("shared", 369, []),
            ("shared", 400, []),
            ("shared", 500, []),
        ],
        [
            ("a", [1]),
            ("b", [1]),
        ],
        [
            ("a", 1),
            ("b", 1),
            ("shared", 369),
        ],
    ),
    Case(
        "Shared deps with interdep versions",
        [
            ("foo", 100, ()),
            ("foo", 101, [("bang", [100])]),
            ("foo", 102, [("whoop", [100])]),
            ("foo", 103, [("zoop", [100])]),
            ("bar", 100, [("foo", [103])]),
            ("bang", 100, []),
            ("whoop", 100, []),
            ("zoop", 100, []),
        ],
        [("foo", range(100, 200)), ("bar", [100])],
        [
            ("bar", 100),
            ("foo", 103),
            ("zoop", 100),
        ],
    ),
    Case(
        "Cycle dep with older version",
        [
            ("a", 1, [("b", [1])]),
            ("a", 2, []),
            ("b", 1, [("a", [2])]),
        ],
        [("a", [1, 2])],
        [
            ("a", 2),  # a@1 is unsatisfiable
        ],
    ),
    Case(
        "Diamond",
        [
            ("a", 100, []),
            ("a", 200, [("c", range(100, 200))]),
            ("b", 100, [("c", range(200, 300))]),
            ("b", 200, [("c", range(300, 400))]),
            ("c", 100, []),
            ("c", 200, []),
            ("c", 300, []),
        ],
        [
            ("a", range(1, 1000)),
            ("b", range(1, 1000)),
        ],
        [
            ("a", 100),
            ("b", 100),
            ("c", 200),
        ],
    ),
    Case(
        "Backtrack over partial satisfier",
        [
            ("a", 100, [("x", range(100, 1000))]),
            ("b", 100, [("x", range(1, 200))]),
            ("c", 100, []),
            ("c", 200, [("a", range(1, 1000)), ("b", range(1, 1000))]),
            ("x", 1, []),
            ("x", 100, [("y", [100])]),
            ("x", 200, []),
            ("y", 100, []),
            ("y", 200, []),
        ],
        [
            ("c", range(1, 1000)),
            ("y", range(200, 1000)),
        ],
        [
            ("c", 100),
            ("y", 200),
        ],
    ),
    Case(
        "Fail: No version for direct requirement",
        [
            ("foo", 200, {}),
            ("foo", 300, {}),
        ],
        [("foo", range(400, 1000))],
        None,
    ),
    Case(
        "Fail: No version matching shared constraints",
        [
            ("foo", 100, [("shared", range(200, 300))]),
            ("bar", 100, [("shared", range(290, 400))]),
            ("shared", 250, []),
            ("shared", 350, []),
        ],
        [
            ("foo", [100]),
            ("bar", [100]),
        ],
        None,
    ),
    Case(
        "Fail: Disjoint constraints",
        [
            ("foo", 100, [("shared", range(0, 201))]),
            ("bar", 200, [("shared", range(300, 999))]),
            ("shared", 100, []),
            ("shared", 500, []),
        ],
        [
            ("foo", [100]),
            ("bar", [100]),
        ],
        None,
    ),
    Case(
        "Fail: Disjoint root constraints",
        [
            ("foo", 100, []),
            ("foo", 200, []),
        ],
        [
            ("foo", [100]),
            ("foo", [200]),
        ],
        None,
    ),
    Case(
        "Fail: Overlapping constraints choose unresolvable package",
        [
            ("foo", 100, [("shared", range(100, 300))]),
            ("bar", 100, [("shared", range(200, 400))]),
            ("shared", 150, []),
            ("shared", 350, []),
            ("shared", 250, [("nonesuch", range(1000))]),
        ],
        [
            ("foo", [100]),
            ("boo", [100]),
        ],
        None,
    ),
    Case(
        "Fail: Overlapping constraints result in a transitive incompatibility",
        [
            ("foo", 1, [("asdf", range(100, 300))]),
            ("bar", 100, [("jklm", range(200, 400))]),
            ("adsf", 200, [("baz", range(300, 400))]),
            ("jklm", 200, [("baz", range(400, 500))]),
            ("baz", 300, []),
            ("baz", 400, []),
        ],
        [
            ("foo", [1]),
            ("bar", [100]),
        ],
        None,
    ),
]


@pytest.mark.parametrize("case_", _CASES, ids=lambda c: c.name)
def test_cases(case_: Case) -> None:
    r = repo(
        {
            pkg(name, version, tuple(dep(dname, frozenset(dvers)) for dname, dvers in deps))
            for name, version, deps in case_.packages
        }
    )
    reqs: list[dep] = [dep(dname, frozenset(dvers)) for dname, dvers in case_.requirements]
    if case_.expected is None:
        with pytest.raises(mod.UnsolvableError) as exc:  # type: ignore
            mod.solve(reqs, r, log=ConsoleLogger())
        list(generate_report(exc.value.incompatibility))  # type: ignore
    else:
        sln = sorted(mod.solve(reqs, r, log=ConsoleLogger()))
        expected = sorted(dep(ename, frozenset({ever})) for ename, ever in case_.expected)
        assert sln == expected
