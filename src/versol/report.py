from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Iterator, Union

from .incompatibility import ConflictCause, Incompatibility, UnavailableCause
from .interfaces import RequirementT
from .term import Term
from .util import T, lazygen, minmax


@lazygen
def generate_report(ic: Incompatibility[RequirementT]) -> ExplainIter[RequirementT]:
    return _generate_for_derived(ic)


@dataclass(frozen=True)
class Dependency(Generic[RequirementT]):
    """
    Dependency
    """

    dependent: RequirementT
    dependens_on: RequirementT


@dataclass(frozen=True)
class Conflict(Generic[RequirementT]):
    """
    Conflict
    """

    a: RequirementT
    b: RequirementT


@dataclass(frozen=True)
class Disallowed(Generic[RequirementT]):
    """
    Disallowed
    """

    requirement: RequirementT


@dataclass(frozen=True)
class Unavailable(Generic[RequirementT]):
    """
    Unavailable
    """

    requirement: RequirementT


@dataclass(frozen=True)
class Needed(Generic[RequirementT]):
    """
    Needed
    """

    requirement: RequirementT


@dataclass(frozen=True)
class Compromise(Generic[RequirementT]):
    """
    Compromise
    """

    left: RequirementT
    right: RequirementT
    result: RequirementT


@dataclass(frozen=True)
class Premise(Generic[T]):
    """
    NewDataclass
    """

    premise: T


@dataclass(frozen=True)
class Conclusion(Generic[T]):
    """
    Conclusion(Generic[T])
    """

    conclusion: T


class NoSolution:
    pass


class Separator:
    pass


Clause = Union[
    Dependency[RequirementT],
    Conflict[RequirementT],
    Disallowed[RequirementT],
    Unavailable[RequirementT],
    Needed[RequirementT],
    Compromise[RequirementT],
]

ConclusionOf = Conclusion[Union[NoSolution, Clause[RequirementT]]]
PremiseOf = Premise[Clause[RequirementT]]

ExplainationPart = Union[Separator, ConclusionOf[RequirementT], PremiseOf[RequirementT]]
ExplainIter = Iterator[ExplainationPart[RequirementT]]


def _generate_for_derived(ic: Incompatibility[RequirementT]) -> ExplainIter[RequirementT]:
    assert isinstance(ic.cause, ConflictCause), ic
    a, b = ic.cause.left, ic.cause.right
    if a.is_derived and b.is_derived:
        yield from _gen_complex(ic, a, b)
    elif a.is_derived:
        yield from _gen_partial(ic, a, b)
    elif b.is_derived:
        yield from _gen_partial(ic, b, a)
    else:
        yield _gen_premise(a)
        yield _gen_premise(b)
        yield _gen_conclusion(ic)


def _gen_conclusion(ic: Incompatibility[RequirementT]) -> ConclusionOf[RequirementT]:
    clz = clause_from_incompatibility(ic)
    return Conclusion(clz)


def _gen_premise(ic: Incompatibility[RequirementT]) -> PremiseOf[RequirementT]:
    clz = clause_from_incompatibility(ic)
    assert not isinstance(clz, NoSolution)
    return Premise(clz)


def _gen_partial(
    ic: Incompatibility[RequirementT],
    derived: Incompatibility[RequirementT],
    external: Incompatibility[RequirementT],
) -> ExplainIter[RequirementT]:
    assert isinstance(derived.cause, ConflictCause)
    d_left, d_right = _conflict_causes(derived.cause)
    if isinstance(d_left.cause, ConflictCause) and not isinstance(d_right.cause, ConflictCause):
        yield from _generate_for_derived(d_left)
        yield _gen_premise(d_right)
        yield _gen_premise(external)
        yield _gen_conclusion(ic)
    elif isinstance(d_right.cause, ConflictCause) and isinstance(d_left.cause, ConflictCause):
        yield from _generate_for_derived(d_right)
        yield _gen_premise(d_left)
        yield _gen_premise(external)
        yield _gen_conclusion(ic)
    else:
        yield from _generate_for_derived(derived)
        yield _gen_premise(external)
        yield _gen_conclusion(ic)


def _gen_complex(
    ic: Incompatibility[RequirementT],
    left: Incompatibility[RequirementT],
    right: Incompatibility[RequirementT],
) -> ExplainIter[RequirementT]:
    assert isinstance(left.cause, ConflictCause) and isinstance(right.cause, ConflictCause), ic
    left_left, left_right = _conflict_causes(left.cause)
    right_left, right_right = _conflict_causes(right.cause)
    if not left_left.is_derived and not left_right.is_derived:
        yield from _generate_for_derived(right)
        yield from _generate_for_derived(left)
        yield _gen_conclusion(ic)
    elif not right_left.is_derived and not right_right.is_derived:
        yield from _generate_for_derived(left)
        yield from _generate_for_derived(right)
        yield _gen_conclusion(ic)
    else:
        yield from _generate_for_derived(left)
        yield Separator()
        yield from _generate_for_derived(right)
        yield Separator()
        yield _gen_premise(left)
        yield _gen_conclusion(ic)


def clause_from_incompatibility(ic: Incompatibility[RequirementT]) -> Clause[RequirementT] | NoSolution:
    if len(ic.terms) == 2:
        t1, t2 = ic.terms
        if t1.positive != t2.positive:
            neg, pos = minmax(t1, t2, key=lambda t: t.positive)
            return Dependency(pos.requirement, neg.requirement)
        elif t1.positive:
            assert t2.positive, ic
            return Conflict(t1.requirement, t2.requirement)
        else:
            assert False, f"Both terms in an incompatibility are negative. Is this even possible? ({ic=})"
    elif len(ic.terms) == 1:
        term = ic.terms[0]
        if term.positive:
            if isinstance(ic.cause, UnavailableCause):
                return Unavailable(term.requirement)
            else:
                return Disallowed(term.requirement)
        else:
            return Needed(term.requirement)
    elif len(ic.terms) == 3:
        a, b, c = ic.terms
        if a.positive and b.positive and not c.positive:
            return Compromise(a.requirement, b.requirement, c.requirement)
        else:
            assert False, f"Unhandled three-term incompatibility in solver error reporting. {ic=}"
    elif not ic.terms:
        return NoSolution()
    else:
        assert False, f"Unhandled case in error reporting {ic=}"


def _conflict_causes(
    cause: ConflictCause[RequirementT],
) -> tuple[Incompatibility[RequirementT], Incompatibility[RequirementT]]:
    return cause.left, cause.right


class Logger(Generic[RequirementT]):
    def message(self, msg: str, *args: Any) -> None:
        assert (msg % args) is not None

    def on_consider(self, selected: RequirementT, requirement: RequirementT, /) -> None:
        self.message("Consider: %r to satisfy %r", selected, requirement)

    def on_select(self, selected: RequirementT, requirement: RequirementT, /) -> None:
        self.message("Selected: %r to satisfy %r", selected, requirement)

    def on_dependency(self, depender: RequirementT, dependency: RequirementT, /):
        self.message("Dependency: %r depends on %r", depender, dependency)

    def on_conflict(self, ic: Incompatibility[RequirementT]):
        self.message("Conflict: %r", ic)

    def on_derive(self, ic: Term[RequirementT]):
        self.message("Derivation: %r", ic)

    def on_backtrack(self, satisfier: Term[RequirementT]):
        self.message("Backtrack: %r is bad", satisfier)

    def on_partial_sln(self, sln: Any):
        self.message("Updated partial solution: %r", sln)


class ConsoleLogger(Logger[RequirementT]):
    def message(self, msg: str, *args: Any) -> None:
        print(msg % args)
