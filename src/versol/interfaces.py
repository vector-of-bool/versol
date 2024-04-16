from __future__ import annotations

from typing import Hashable, Iterable, Protocol, TypeVar

from typing_extensions import Self

from .util import LessThanOrdered


class IKey(LessThanOrdered, Hashable, Protocol): ...


class IRequirement(Protocol):
    """
    Abstract interface for requirement objects used by the solver.

    Implement these interfaces to customize the types used by the solver.

    .. seealso:: :mod:`pubgrub.iset`
    """

    @property
    def key(self) -> IKey:
        """
        A unique identifier for the group of objects that this requirement matches.
        Should be a hashable and orderable type.
        """
        ...

    def implied_by(self, other: Self, /) -> bool:
        """
        Return `True` iff the requirement ``other`` would satisfy ``self``.
        """
        ...

    def intersection(self, other: Self, /) -> Self:
        """
        Return a new requirement that would satisfy both ``self`` and ``other``.
        """
        ...

    def difference(self, other: Self, /) -> Self:
        """
        Return a new requirement that satisfies ``self`` but never satisfies ``other``.
        """
        ...

    def union(self, other: Self, /) -> Self:
        """
        Return a new requirement that would satisfy ``self``, satisfy ``other``, or satisfy both.
        """
        ...

    @property
    def intrinsically_unsatisfiable(self) -> bool:
        """
        Return `True` if the requirement is intrinsically unsatisfiable (e.g an empty requirement)
        """
        ...


RequirementT = TypeVar("RequirementT", bound=IRequirement)
"""Type parameter that is bound to an `IRequirement` type"""


def excludes(a: IRequirement, b: IRequirement) -> bool:
    """
    Return `True` if the two given requirements are mutually exclusive.
    """
    return a.intersection(b).intrinsically_unsatisfiable


class IRequirementProvider(Protocol[RequirementT]):
    """
    Interface of a type that provides requirement information. Use to customize
    the type of the objects that are "solved"
    """

    def best_candidate(self, req: RequirementT, /) -> None | tuple[RequirementT, Iterable[RequirementT]]:
        """
        Find a single-version requirement that best matches the given requirement.
        The return value should be a tuple of two elements:

        1. A precise requirement that corresponds to the object that is judged as
           the best match for the given requirement ``req``.
        2. An iterable of the dependencies for the requirement returned as the
           first pair element.

        The returned requirement should optimally only match a single object.
        """
        ...
