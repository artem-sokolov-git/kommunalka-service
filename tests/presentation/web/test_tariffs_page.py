from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def services(client: TestClient, household: dict[str, Any]) -> dict[str, str]:
    return {service["name"]: service["id"] for service in client.get("/services").json()}


def change(client: TestClient, service_id: str, price: str, month: str) -> str:
    response = client.post(
        f"/view/tariffs/{service_id}",
        data={"price": price, "month": month},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client.get(response.headers["location"]).text


def test_lists_prices_with_the_current_one(client: TestClient, services: dict[str, str]) -> None:
    page = client.get("/view/tariffs").text

    assert "Транспортировка газа" in page
    assert "в месяц" in page
    assert "за м³" in page
    assert "действует с 1\u00a0декабря 2025" in page
    assert "300,78" in page
    assert 'placeholder="300,78"' in page
    assert 'value="2027-01"' in page


def test_changes_price_from_a_month(client: TestClient, services: dict[str, str]) -> None:
    page = change(client, services["Транспортировка газа"], "320", "2027-01")

    assert "Транспортировка газа: 300,78 → 320,00 с 1\u00a0января 2027" in page
    assert "С 1\u00a0января 2027 — 320,00 грн в месяц" in page


def test_undoes_price_change(client: TestClient, services: dict[str, str]) -> None:
    transport = services["Транспортировка газа"]
    change(client, transport, "320", "2027-01")

    response = client.post(f"/view/tariffs/{transport}/undo", follow_redirects=False)

    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "новая цена отменена, действует 300,78" in page
    [period] = client.get(f"/services/{transport}/tariffs").json()
    assert (period["price"], period["valid_to"]) == ("300.78", None)


def test_lists_older_prices_by_month(client: TestClient, services: dict[str, str]) -> None:
    change(client, services["Транспортировка газа"], "310", "2026-10")

    page = client.get("/view/tariffs").text

    assert "Прежние цены · 1" in page
    assert "декабрь 2025 — сентябрь 2026" in page


@pytest.mark.parametrize(
    ("price", "month", "message"),
    [
        ("320", "2026-09", "Счёт за сентябрь 2026 уже выставлен по текущей цене"),
        ("abc", "2027-01", "не число «abc»"),
        ("320", "2025-12", "Новая цена должна начинаться позже 01.12.2025"),
    ],
)
def test_rejects_bad_price_change(
    client: TestClient, services: dict[str, str], price: str, month: str, message: str
) -> None:
    page = change(client, services["Транспортировка газа"], price, month)

    assert message in page


def test_bill_takes_a_ready_amount_instead_of_the_tariff(
    client: TestClient, household: dict[str, Any], services: dict[str, str]
) -> None:
    [meter] = client.get(f"/households/{household['id']}/meters").json()
    client.post(
        f"/view/households/{household['id']}/readings",
        data={"taken_on": "2026-11-03", "meter_id": [meter["id"]], "value": ["41800"]},
    )
    page = client.get(f"/view/households/{household['id']}/readings").text
    assert 'name="fixed_amount" inputmode="decimal" value="300,78"' in page

    transport = services["Транспортировка газа"]
    client.post(
        f"/view/households/{household['id']}/bills",
        data={
            "year": "2026",
            "month": "10",
            "fixed_service_id": [transport],
            "fixed_amount": ["295,10"],
        },
    )

    bill = client.get(f"/households/{household['id']}/bills/2026/10").json()
    amounts = {line["service_id"]: line["amount"] for line in bill["lines"]}
    assert amounts[transport] == "295.10"
    assert client.get(f"/services/{transport}/tariffs").json()[-1]["price"] == "300.78"
