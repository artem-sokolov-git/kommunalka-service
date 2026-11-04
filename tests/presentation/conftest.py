from typing import Any

import pytest
from fastapi.testclient import TestClient


def post(client: TestClient, url: str, body: dict[str, Any]) -> Any:
    response = client.post(url, json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def household(client: TestClient) -> dict[str, Any]:
    household = post(client, "/households", {"name": "Дом <b>", "address": "ул. Круглая 1"})
    gas = post(client, "/services", {"name": "Газ", "unit": "m3"})
    transport = post(client, "/services", {"name": "Транспортировка газа"})
    post(client, f"/services/{gas['id']}/tariffs", {"price": "7.96", "valid_from": "2024-09-01"})
    post(
        client,
        f"/services/{transport['id']}/tariffs",
        {"price": "300.78", "valid_from": "2025-12-01"},
    )
    meter = post(
        client,
        f"/households/{household['id']}/meters",
        {
            "service_id": gas["id"],
            "serial_number": "566336",
            "label": "Газовый",
            "installed_on": "2026-01-01",
        },
    )
    for taken_on, value in (
        ("2026-08-01", "41715"),
        ("2026-09-01", "41739"),
        ("2026-10-01", "41768"),
    ):
        post(client, f"/meters/{meter['id']}/readings", {"value": value, "taken_on": taken_on})
    for month in (8, 9):
        post(client, f"/households/{household['id']}/bills", {"year": 2026, "month": month})
    return household
