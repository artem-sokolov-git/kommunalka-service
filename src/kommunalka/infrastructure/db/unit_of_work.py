from types import TracebackType
from typing import Self

from sqlalchemy import Connection, Engine, RootTransaction

from kommunalka.infrastructure.db.repositories import (
    SqlBillRepository,
    SqlHouseholdRepository,
    SqlMeterRepository,
    SqlReadingRepository,
    SqlServiceRepository,
    SqlTariffPeriodRepository,
)


class SqlUnitOfWork:
    """One connection and transaction per `with` block."""

    households: SqlHouseholdRepository
    services: SqlServiceRepository
    meters: SqlMeterRepository
    readings: SqlReadingRepository
    tariff_periods: SqlTariffPeriodRepository
    bills: SqlBillRepository

    _connection: Connection
    _transaction: RootTransaction

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def __enter__(self) -> Self:
        self._connection = self._engine.connect()
        self._transaction = self._connection.begin()
        self.households = SqlHouseholdRepository(self._connection)
        self.services = SqlServiceRepository(self._connection)
        self.meters = SqlMeterRepository(self._connection)
        self.readings = SqlReadingRepository(self._connection)
        self.tariff_periods = SqlTariffPeriodRepository(self._connection)
        self.bills = SqlBillRepository(self._connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._transaction.is_active:
                self._transaction.rollback()
        finally:
            self._connection.close()

    def commit(self) -> None:
        self._transaction.commit()

    def rollback(self) -> None:
        self._transaction.rollback()
