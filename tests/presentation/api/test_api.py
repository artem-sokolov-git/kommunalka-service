from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def post(client: TestClient, url: str, body: dict[str, Any], expected: int = 201) -> Any:
    response = client.post(url, json=body)
    assert response.status_code == expected, response.text
    return response.json()


@pytest.fixture
def household(client: TestClient) -> dict[str, Any]:
    return post(client, "/households", {"name": "Home", "address": "Main st, 1"})


@pytest.fixture
def gas(client: TestClient) -> dict[str, Any]:
    return post(client, "/services", {"name": "Gas", "unit": "m3"})


@pytest.fixture
def transport(client: TestClient) -> dict[str, Any]:
    return post(client, "/services", {"name": "Gas transportation"})


@pytest.fixture
def gas_meter(client: TestClient, household: dict[str, Any], gas: dict[str, Any]) -> dict[str, Any]:
    return post(
        client,
        f"/households/{household['id']}/meters",
        {
            "service_id": gas["id"],
            "serial_number": "G-1",
            "label": "Boiler",
            "installed_on": "2025-01-01",
        },
    )


def test_full_billing_flow(
    client: TestClient,
    household: dict[str, Any],
    gas: dict[str, Any],
    transport: dict[str, Any],
    gas_meter: dict[str, Any],
) -> None:
    post(
        client,
        f"/services/{gas['id']}/tariffs",
        {"price": "0.78", "valid_from": "2026-01-01", "valid_to": "2026-12-31"},
    )
    post(client, f"/meters/{gas_meter['id']}/readings", {"value": "100", "taken_on": "2026-09-02"})
    reading = post(
        client, f"/meters/{gas_meter['id']}/readings", {"value": "142.5", "taken_on": "2026-10-03"}
    )
    assert reading["previous_taken_on"] == "2026-09-02"

    bill = post(
        client,
        f"/households/{household['id']}/bills",
        {"year": 2026, "month": 9, "fixed_amounts": {transport["id"]: "12.30"}},
    )

    assert bill["period_start"] == "2026-09-01"
    assert bill["period_end"] == "2026-09-30"
    assert bill["total"] == "45.45"
    assert sorted(bill["lines"], key=lambda line: line["kind"]) == [
        {
            "kind": "fixed",
            "service_id": transport["id"],
            "service_name": "Gas transportation",
            "amount": "12.30",
        },
        {
            "kind": "metered",
            "service_id": gas["id"],
            "service_name": "Gas",
            "quantity": "42.5",
            "price": "0.78",
            "amount": "33.15",
        },
    ]
    assert client.get(f"/households/{household['id']}/bills").json() == [bill]
    assert client.get(f"/households/{household['id']}/bills/2026/9").json() == bill


def test_reads_resources(
    client: TestClient,
    household: dict[str, Any],
    gas: dict[str, Any],
    gas_meter: dict[str, Any],
) -> None:
    assert client.get("/households").json() == [household]
    assert client.get(f"/households/{household['id']}").json() == household
    assert gas in client.get("/services").json()
    assert gas["is_metered"] is True
    assert client.get(f"/households/{household['id']}/meters").json() == [gas_meter]
    assert client.get(f"/meters/{gas_meter['id']}/readings").json() == []
    assert client.get(f"/services/{gas['id']}/tariffs").json() == []


def test_corrects_reading(client: TestClient, gas_meter: dict[str, Any]) -> None:
    reading = post(
        client, f"/meters/{gas_meter['id']}/readings", {"value": "100", "taken_on": "2026-09-02"}
    )

    response = client.patch(f"/readings/{reading['id']}", json={"value": "101.5"})

    assert response.status_code == 200
    assert response.json()["value"] == "101.5"


def test_removes_meter(client: TestClient, gas_meter: dict[str, Any]) -> None:
    meter = post(
        client, f"/meters/{gas_meter['id']}/removal", {"removed_on": "2026-10-15"}, expected=200
    )

    assert meter["removed_on"] == "2026-10-15"
    assert meter["is_active"] is False


def test_unknown_household_is_404(client: TestClient) -> None:
    response = client.get(f"/households/{uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_duplicate_is_409(client: TestClient, household: dict[str, Any]) -> None:
    post(client, "/households", {"name": "Other", "address": household["address"]}, expected=409)


def test_domain_rule_violation_is_422(client: TestClient, gas_meter: dict[str, Any]) -> None:
    post(client, f"/meters/{gas_meter['id']}/readings", {"value": "100", "taken_on": "2026-09-02"})

    response = client.post(
        f"/meters/{gas_meter['id']}/readings", json={"value": "99", "taken_on": "2026-10-02"}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Reading value decreased"}


def test_missing_reading_for_bill_is_422(client: TestClient, household: dict[str, Any]) -> None:
    gas = post(client, "/services", {"name": "Gas", "unit": "m3"})
    post(
        client,
        f"/households/{household['id']}/meters",
        {
            "service_id": gas["id"],
            "serial_number": "G-1",
            "label": "B",
            "installed_on": "2025-01-01",
        },
    )

    post(client, f"/households/{household['id']}/bills", {"year": 2026, "month": 9}, expected=422)


def test_rejects_unknown_fields(client: TestClient) -> None:
    post(client, "/households", {"name": "Home", "address": "A", "extra": 1}, expected=422)


def test_missing_bill_is_404(client: TestClient, household: dict[str, Any]) -> None:
    response = client.get(f"/households/{household['id']}/bills/2026/9")

    assert response.status_code == 404
    assert response.json() == {"detail": "Bill for 2026-09 not found"}


@pytest.mark.parametrize("month", [0, 13])
def test_rejects_invalid_month(client: TestClient, household: dict[str, Any], month: int) -> None:
    assert client.get(f"/households/{household['id']}/bills/2026/{month}").status_code == 422
    post(
        client,
        f"/households/{household['id']}/bills",
        {"year": 2026, "month": month},
        expected=422,
    )


def test_changes_price(client: TestClient, gas: dict[str, Any]) -> None:
    post(client, f"/services/{gas['id']}/tariffs", {"price": "0.78", "valid_from": "2026-01-01"})

    new = post(
        client, f"/services/{gas['id']}/prices", {"price": "0.85", "valid_from": "2027-01-01"}
    )

    assert new["valid_to"] is None
    periods = client.get(f"/services/{gas['id']}/tariffs").json()
    assert [(p["valid_from"], p["valid_to"]) for p in periods] == [
        ("2026-01-01", "2026-12-31"),
        ("2027-01-01", None),
    ]
