class DomainError(ValueError):
    """Base error for domain rule violations."""


class DuplicateBillError(DomainError):
    """Household already has a bill for the billing month."""


class DuplicateHouseholdError(DomainError):
    """Household address is already taken."""


class DuplicateMeterError(DomainError):
    """Meter serial number or label is already taken."""


class DuplicateReadingError(DomainError):
    """Meter already has a reading for the billing month."""


class FutureReadingError(DomainError):
    """Reading is dated after today."""


class MissingReadingError(DomainError):
    """Meter has no reading required for the calculation."""


class MissingTariffError(DomainError):
    """No tariff period covers the billing month."""


class OverlappingTariffPeriodError(DomainError):
    """Tariff period overlaps with another one of the same service."""


class PeriodAlreadyBilledError(DomainError):
    """Household month is already billed, its readings can't change."""
