from __future__ import annotations

import copy
import enum
from typing import Generic

from .interfaces import IKey, RequirementT, excludes


class Term(Generic[RequirementT]):
    def __init__(self, req: RequirementT, positive: bool) -> None:
        self.__requirement = copy.copy(req)
        self.__positive = positive

    @property
    def key(self) -> IKey:
        return self.__requirement.key

    @property
    def requirement(self) -> RequirementT:
        return self.__requirement

    @property
    def inverse(self) -> Term[RequirementT]:
        return Term(self.requirement, not self.positive)

    @property
    def positive(self) -> bool:
        return self.__positive

    def __copy__(self) -> Term[RequirementT]:
        return Term(self.requirement, self.positive)

    def intersection(self, other: Term[RequirementT]) -> Term[RequirementT]:
        if self.positive and other.positive:
            isect = self.requirement.intersection(other.requirement)
            return Term(isect, True)
        if not self.positive and not other.positive:
            un = self.requirement.union(other.requirement)
            if un.intrinsically_unsatisfiable:
                # Less happy path...
                # a: %%%%%%%%----------%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                # b: %%%%%%%%%%%%%%%%%%%%%%%%%%-----------%%%%%%%%%
                # r: %%%%%%%%----------%%%%%%%%-----------%%%%%%%%%
                # The above `r` is unrepresentable with a single term, but we _can_ represent the two
                # outer ranges as a single negative range and discard the inner positive range:
                # -- const auto& low  = (std::min)(range().low(), other.range().low());
                # -- const auto& high = (std::max)(range().high(), other.range().high());
                # -- return term{name, range{low, high}, false};
                # But this is still funadmentally incorrect. Assuming the pubgrub
                # algorithm never gets us in such a situation, we'll assume that this
                # path won't be taken in normal code.
                assert False, "Faulty assumption in the pubgrub algorithm implementation. This is a BUG!"
            return Term(un, False)
        if not self.positive:
            return other.intersection(self)

        assert not other.positive
        diff = self.requirement.difference(other.requirement)
        return Term(diff, True)

    @property
    def intrinsically_unsatisfiable(self) -> bool:
        if self.requirement.intrinsically_unsatisfiable:
            return self.positive
        return False

    def difference(self, other: Term[RequirementT]) -> Term[RequirementT]:
        return self.intersection(other.inverse)

    def implies(self, other: Term[RequirementT]) -> bool:
        return other.implied_by(self)

    def implied_by(self, other: Term[RequirementT]) -> bool:
        if self.key != other.key:
            return False
        if self.positive:
            if other.positive:
                return self.requirement.implied_by(other.requirement)
        if other.positive:
            return excludes(self.requirement, other.requirement)
        # Both ranges are negative
        return other.requirement.implied_by(self.requirement)

    def excludes(self, other: Term[RequirementT]) -> bool:
        if self.key != other.key:
            # Unrelated terms cannot exclude each other
            return False
        if self.positive:
            if other.positive:
                return excludes(self.requirement, other.requirement)
            else:
                return other.excludes(self)
        if other.positive:
            return self.requirement.implied_by(other.requirement)
        # Both terms are negative, and it is not possible that they exclude each other
        return False

    def relation_to(self, other: Term[RequirementT]) -> SetRelation:
        if self.implies(other):
            return SetRelation.Subset
        elif self.excludes(other):
            return SetRelation.Disjoint
        else:
            return SetRelation.Overlap

    def __repr__(self) -> str:
        if self.positive:
            return f"<Term {self.requirement!r}>"
        else:
            return f"<Term ¬ {self.requirement!r}>"


class SetRelation(enum.Enum):
    Disjoint = 1
    Overlap = 2
    Subset = 3
