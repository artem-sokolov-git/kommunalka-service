from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import DomainError, DuplicateHouseholdError


@dataclass(frozen=True, slots=True, kw_only=True)
class Household:
    """Billed party that owns meters and receives bills."""

    name: str
    address: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainError("Household name must not be empty")
        if not self.address.strip():
            raise DomainError("Household address must not be empty")


def ensure_unique_household(household: Household, existing: Iterable[Household]) -> None:
    """Raise if another household has the same address."""
    for other in existing:
        if other.id != household.id and other.address == household.address:
            raise DuplicateHouseholdError(f"Address {household.address!r} is already taken")
