from __future__ import annotations

import functools
import itertools
from dataclasses import dataclass
from typing import Generic, Iterable, Sequence

from typing_extensions import TypeAlias

from .interfaces import RequirementT
from .term import Term


@dataclass(frozen=True)
class RootCause:
    """
    RootCause
    """


@dataclass(frozen=True)
class UnavailableCause:
    """
    UnavailableCause
    """


@dataclass(frozen=True)
class DependencyCause:
    """
    DependencyCause
    """


@dataclass(frozen=True)
class ConflictCause(Generic[RequirementT]):
    """
    Conflict
    """

    left: Incompatibility[RequirementT]
    right: Incompatibility[RequirementT]


Cause: TypeAlias = "RootCause | UnavailableCause | DependencyCause | ConflictCause[RequirementT]"


class Incompatibility(Generic[RequirementT]):

    def __init__(
        self,
        terms: Iterable[Term[RequirementT]],
        cause: Cause[RequirementT],
    ) -> None:
        self.__terms = tuple(_simplify(terms))
        self.__cause = cause

    @property
    def terms(self) -> Sequence[Term[RequirementT]]:
        return self.__terms

    @property
    def cause(self) -> Cause[RequirementT]:
        return self.__cause

    def __repr__(self) -> str:
        conj = " ∧ ".join(map(repr, self.terms))
        return f"<Incompatibility {{{conj}}} by {self.cause!r}>"

    @property
    def is_derived(self) -> bool:
        """
        `True` if this incompatibility was generated by a conflict resolution.
        """
        return isinstance(self.cause, ConflictCause)


def _simplify(terms: Iterable[Term[RequirementT]]) -> Iterable[Term[RequirementT]]:
    """
    Reduce the given terms so that each term key has only one corresponding term
    in the resulting set.
    """
    terms = list(terms)
    terms.sort(key=lambda k: k.key)
    grouped = itertools.groupby(terms, key=lambda t: t.key)
    for _key, terms_for_key in grouped:
        yield functools.reduce(_not_null_intersection, terms_for_key)


def _not_null_intersection(a: Term[RequirementT], b: Term[RequirementT]) -> Term[RequirementT]:
    """Return the intersection of two terms, asserting that it is non-empty"""
    isect = a.intersection(b)
    assert isect is not None, f"Expected a non-empty intersection [{a=}, {b=}]"
    return isect
