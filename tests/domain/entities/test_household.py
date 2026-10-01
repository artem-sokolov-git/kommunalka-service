import pytest

from kommunalka.domain import (
    DomainError,
    DuplicateHouseholdError,
    Household,
    ensure_unique_household,
)


@pytest.mark.parametrize(("name", "address"), [(" ", "Main st, 1"), ("Home", " ")])
def test_rejects_empty_fields(name: str, address: str) -> None:
    with pytest.raises(DomainError):
        Household(name=name, address=address)


def test_address_must_be_unique() -> None:
    home = Household(name="Home", address="Main st, 1")
    other = Household(name="Other", address="Main st, 1")

    ensure_unique_household(home, [home])
    with pytest.raises(DuplicateHouseholdError):
        ensure_unique_household(other, [home])
