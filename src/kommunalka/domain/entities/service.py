from dataclasses import dataclass, field
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import DomainError
from kommunalka.domain.value_objects import Unit


@dataclass(frozen=True, slots=True, kw_only=True)
class Service:
    """Utility service, e.g. electricity or cold water.

    A service without a unit is unmetered: its bill amount comes ready, e.g. gas transportation.
    """

    name: str
    unit: Unit | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainError("Service name must not be empty")

    @property
    def is_metered(self) -> bool:
        return self.unit is not None
