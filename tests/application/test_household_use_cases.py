import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import register_household
from kommunalka.domain import DuplicateHouseholdError, Household


def test_registers_household(uow: UnitOfWork) -> None:
    household = register_household(uow, name="Home", address="Main st, 1")

    assert uow.households.get(household.id) == household


def test_rejects_duplicate_address(uow: UnitOfWork, household: Household) -> None:
    with pytest.raises(DuplicateHouseholdError):
        register_household(uow, name="Other", address=household.address)

    assert uow.households.list_all() == [household]
