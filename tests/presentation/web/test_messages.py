import pytest

from kommunalka.presentation.web.messages import translate


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Газовый: Reading value decreased", "Газовый: показание меньше предыдущего"),
        (
            "Meter 'Газовый' is not in service on 2027-01-02",
            "Счётчик «Газовый» не работает на 02.01.2027",
        ),
        (
            "2026-09 is already billed",
            "Счёт за сентябрь 2026 уже выставлен, показания этого месяца менять нельзя",
        ),
        ("No tariff for service 7be1ab9e-4bde in 2026-10", "Нет тарифа на октябрь 2026"),
        ("Household 2b81c283-9857-4fe2-913a-c7f0506cd65f not found", "Не найдено"),
        ("Something new", "Something new"),
    ],
)
def test_translates_messages(message: str, expected: str) -> None:
    assert translate(message) == expected
