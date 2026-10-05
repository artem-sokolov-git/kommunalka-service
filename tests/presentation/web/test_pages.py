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


def test_renders_bill(client: TestClient, household: dict[str, Any]) -> None:
    response = client.get(f"/view/households/{household['id']}/bills/2026/9")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    page = response.text
    assert "Счёт за сентябрь 2026" in page
    assert "Газовый: 41\u00a0739 → 41\u00a0768" in page
    assert "29 м³" in page
    assert "230,84" in page
    assert "Транспортировка газа" in page
    assert "531,62" in page
    assert f'href="http://testserver/view/households/{household["id"]}/bills/2026/8"' in page


def test_escapes_user_input(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(f"/view/households/{household['id']}/bills/2026/9").text

    assert "Дом &lt;b&gt;" in page
    assert "Дом <b>" not in page


@pytest.mark.parametrize("month", ["10", "13"])
def test_missing_bill_page_is_html_404(
    client: TestClient, household: dict[str, Any], month: str
) -> None:
    response = client.get(f"/view/households/{household['id']}/bills/2026/{month}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Не найдено</h1>" in response.text


def test_api_errors_stay_json(client: TestClient, household: dict[str, Any]) -> None:
    response = client.get(f"/households/{household['id']}/bills/2026/10")

    assert response.status_code == 404
    assert response.json() == {"detail": "Bill for 2026-10 not found"}


def test_home_lists_households(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get("/").text

    assert "ул. Круглая 1" in page
    assert f'href="http://testserver/view/households/{household["id"]}/bills"' in page
    assert "Последний счёт: сентябрь 2026 · всего 2" in page


def test_home_without_households(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Домохозяйств пока нет" in response.text


def test_bills_page_groups_bills_by_year(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(f"/view/households/{household['id']}/bills").text

    assert page.index("Сентябрь") < page.index("Август")
    assert f'href="http://testserver/view/households/{household["id"]}/bills/2026/9"' in page
    assert "<span>2026</span>" in page


def test_bill_page_links_back(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(f"/view/households/{household['id']}/bills/2026/9").text

    assert 'href="http://testserver/"' in page
    assert f'href="http://testserver/view/households/{household["id"]}/bills"' in page


def test_serves_stylesheet(client: TestClient) -> None:
    page = client.get("/").text
    response = client.get("/static/style.css")

    assert 'href="http://testserver/static/style.css"' in page
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
