from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, Sequence

from typing_extensions import TypeAlias

from ._solution import PartialSolution
from .incompatibility import ConflictCause, DependencyCause, Incompatibility, RootCause, UnavailableCause
from .interfaces import IKey, IRequirementProvider, RequirementT
from .term import SetRelation, Term
from .report import Logger


def solve(
    requirements: Iterable[RequirementT],
    provider: IRequirementProvider[RequirementT],
    *,
    log: Logger[RequirementT] = Logger(),
) -> Iterable[RequirementT]:
    """
    Perform dependency resolution.

    :param requirements: Zero or more requirements that act as the basis for
        dependency resolution. See `IRequirement` for more information on the
        requirement interface.
    :param provider: An object that can be used to look up the information on
        requirements. Refer to the `IRequirementProvider` protocol for
        information on implementing a custom provider.
    :param log: An object that implements the `Logger` interface. This allows
        the
    """
    sol = _Solver(provider, log)
    for r in requirements:
        sol.preload_root(r)
    return sol.solve()


@dataclass(frozen=True)
class _AlmostConflict(Generic[RequirementT]):
    """
    _AlmostConflict
    """

    term: Term[RequirementT]


class NoConflict:
    pass


class Conflict:
    pass


ConflictResult: TypeAlias = "_AlmostConflict[RequirementT] | NoConflict | Conflict"


class _IncompatRecord(Generic[RequirementT]):
    def __init__(self) -> None:
        self.__incompats: list[Incompatibility[RequirementT]] = []
        self.__by_key: dict[IKey, list[Incompatibility[RequirementT]]] = {}

    def add(self, ic: Incompatibility[RequirementT]) -> Incompatibility[RequirementT]:
        self.__incompats.append(ic)
        for t in ic.terms:
            for_key = self.__by_key.setdefault(t.key, [])
            for_key.append(ic)
        return ic

    def for_key(self, key: IKey) -> Sequence[Incompatibility[RequirementT]]:
        return self.__by_key.get(key, ())


class _Solver(Generic[RequirementT]):
    def __init__(self, prov: IRequirementProvider[RequirementT], log: Logger[RequirementT]) -> None:
        self.__provider = prov
        self.__incompats = _IncompatRecord[RequirementT]()
        self.__changed: list[IKey] = []
        self.__sln = PartialSolution[RequirementT]()
        self.log = log

    def preload_root(self, req: RequirementT) -> None:
        self.__incompats.add(Incompatibility([Term(req, False)], RootCause()))
        self.__changed.append(req.key)

    def solve(self) -> Iterable[RequirementT]:
        while self.__changed:
            self.unit_propagation()
            self.speculate_one_decision()
        return self.__sln.solution()

    def speculate_one_decision(self) -> None:
        next_unsat = self.__sln.next_unsatisfied_requirement()
        if next_unsat is None:
            return
        candidate = self.__provider.best_candidate(next_unsat)
        if candidate is None:
            # The provider has no candidates for this requirement, so this requirement
            # is incompatiblbe with the full solution
            self.__incompats.add(Incompatibility([Term(next_unsat, True)], UnavailableCause()))
            self.__changed.append(next_unsat.key)
            return
        cand_req, cand_deps = candidate
        self.log.on_consider(cand_req, next_unsat)

        found_conflict = False
        ic = None
        for dep in cand_deps:
            self.log.on_dependency(cand_req, dep)
            if dep.key == cand_req.key:
                raise RuntimeError(f"Requirement [{cand_req=}] depends on itself [{dep=}]")
            ic = Incompatibility([Term(cand_req, True), Term(dep, False)], DependencyCause())
            self.__incompats.add(ic)
            this_conflicts = all(ic_term.key == cand_req.key or self.__sln.satisfies(ic_term) for ic_term in ic.terms)
            if this_conflicts:
                self.log.on_conflict(ic)
            found_conflict = found_conflict or this_conflicts

        if not found_conflict:
            self.log.on_select(cand_req, next_unsat)
            self.__sln.record_decision(Term(cand_req, True))
            self.log.on_partial_sln(self.__sln)
        self.__changed.append(cand_req.key)

    def unit_propagation(self) -> None:
        while self.__changed:
            unit = self.__changed.pop()
            self.propagate_for_key(unit)

    def propagate_for_key(self, key: IKey) -> None:
        ics = list(self.__incompats.for_key(key))
        for ic in ics:
            if not self.propagate_ic(ic):
                break

    def propagate_ic(self, ic: Incompatibility[RequirementT]) -> bool:
        res = self.check_conflict(ic)
        if isinstance(res, _AlmostConflict):
            inv = res.term.inverse
            self.log.on_derive(inv)
            self.__sln.record_derivation(inv, ic)
            self.__changed.append(inv.key)
            return True
        elif isinstance(res, Conflict):
            cause = self.resolve_conflict(ic)
            res = self.check_conflict(cause)
            assert isinstance(res, _AlmostConflict), (
                "Expected conflict resolution term to be an almost-conflict with the "
                "partial solution so that we can make a subsequent derivation from it"
                f" [{ic=}, {cause=}, {res=}]"
            )
            inv = res.term.inverse
            self.log.on_derive(inv)
            self.__sln.record_derivation(inv, cause)
            self.__changed = [inv.key]
            return False
        else:
            assert isinstance(res, NoConflict)
            # Nothing to do
            return True

    def check_conflict(self, ic: Incompatibility[RequirementT]) -> ConflictResult[RequirementT]:
        unsat_term: None | Term[RequirementT] = None
        for term in ic.terms:
            rel = self.__sln.relation_to(term)
            if rel is SetRelation.Disjoint:
                return NoConflict()
            elif rel is SetRelation.Overlap:
                if unsat_term is not None:
                    return NoConflict()
                unsat_term = term
            else:
                # Term is satisfied. Nothing to do
                pass

        if unsat_term is None:
            return Conflict()

        return _AlmostConflict(unsat_term)

    def resolve_conflict(self, ic: Incompatibility[RequirementT]) -> Incompatibility[RequirementT]:
        self.log.on_conflict(ic)
        while True:
            bt_info = self.__sln.create_backtrack_info(ic)
            if bt_info is None:
                raise UnsolvableError(ic)
            if bt_info.satisfier.is_decision or bt_info.prev_sat_level < bt_info.satisfier.decision_level:
                self.log.on_backtrack(bt_info.satisfier.term)
                self.__sln.backtrack_to(bt_info.prev_sat_level)
                return ic
            assert bt_info.satisfier.cause is not None
            new_terms = [t for t in ic.terms if t is not bt_info.term]
            if bt_info.difference is not None:
                new_terms.append(bt_info.difference.inverse)
            assert all(self.__sln.satisfies(t) for t in new_terms)
            ic = self.__incompats.add(Incompatibility(new_terms, ConflictCause(ic, bt_info.satisfier.cause)))
            assert isinstance(self.check_conflict(ic), Conflict)


class UnsolvableError(Generic[RequirementT], RuntimeError):
    def __init__(self, ic: Incompatibility[RequirementT]) -> None:
        self.__root = ic

    @property
    def incompatibility(self) -> Incompatibility[RequirementT]:
        return self.__root
