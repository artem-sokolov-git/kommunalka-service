import pytest

from kommunalka.domain import DomainError, Service, Unit


def test_service_with_unit_is_metered() -> None:
    assert Service(name="Gas", unit=Unit.CUBIC_METER).is_metered
    assert not Service(name="Gas transportation").is_metered


def test_rejects_empty_name() -> None:
    with pytest.raises(DomainError):
        Service(name=" ")
