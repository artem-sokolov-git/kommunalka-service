from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.domain import Service, Unit


def add_service(uow: UnitOfWork, *, name: str, unit: Unit | None = None) -> Service:
    service = Service(name=name, unit=unit)
    with uow:
        uow.services.save(service)
        uow.commit()
    return service
