from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.domain import Household, ensure_unique_household


def register_household(uow: UnitOfWork, *, name: str, address: str) -> Household:
    household = Household(name=name, address=address)
    with uow:
        ensure_unique_household(household, uow.households.list_all())
        uow.households.save(household)
        uow.commit()
    return household
