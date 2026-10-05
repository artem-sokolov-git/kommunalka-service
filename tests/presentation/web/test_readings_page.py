from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def meter(client: TestClient, household: dict[str, Any]) -> dict[str, Any]:
    [meter] = client.get(f"/households/{household['id']}/meters").json()
    return meter


def readings_url(household: dict[str, Any]) -> str:
    return f"/view/households/{household['id']}/readings"


def submit(client: TestClient, household: dict[str, Any], meter: dict[str, Any], value: str) -> Any:
    return client.post(
        readings_url(household),
        data={"taken_on": "2026-11-03", "meter_id": [meter["id"]], "value": [value]},
        follow_redirects=False,
    )


def test_shows_meters_with_last_reading(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(readings_url(household), params={"taken_on": "2026-11-03"}).text

    assert "Газовый" in page
    assert "41\u00a0768 м³" in page
    assert "01.10.2026" in page
    assert "Счёт за октябрь 2026" in page
    assert "Выставить счёт" in page


def test_links_to_issued_bill(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(readings_url(household), params={"taken_on": "2026-10-05"}).text

    assert "Счёт за сентябрь 2026" in page
    assert f"/view/households/{household['id']}/bills/2026/9" in page
    assert "Выставить счёт" not in page


def test_saves_readings_and_redirects(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any]
) -> None:
    response = submit(client, household, meter, "41 800,5")

    assert response.status_code == 303
    page = client.get(response.headers["location"]).text
    assert "Показания сохранены" in page
    readings = client.get(f"/meters/{meter['id']}/readings").json()
    assert readings[-1]["value"] == "41800.5"
    assert readings[-1]["taken_on"] == "2026-11-03"


@pytest.mark.parametrize(
    ("value", "message"),
    [("41000", "Газовый: Reading value decreased"), ("abc", "Не число"), ("", "хотя бы одно")],
)
def test_rejects_bad_input_keeping_it(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any], value: str, message: str
) -> None:
    response = submit(client, household, meter, value)

    assert response.status_code == 422
    assert message in response.text
    assert f'value="{value}"' in response.text
    assert len(client.get(f"/meters/{meter['id']}/readings").json()) == 3


def test_issues_bill_after_readings(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any]
) -> None:
    submit(client, household, meter, "41800")

    response = client.post(
        f"/view/households/{household['id']}/bills",
        data={"year": "2026", "month": "10", "taken_on": "2026-11-03"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/view/households/{household['id']}/bills/2026/10"
    )
    assert client.get(response.headers["location"]).status_code == 200


def test_bill_error_is_shown_on_the_page(client: TestClient, household: dict[str, Any]) -> None:
    response = client.post(
        f"/view/households/{household['id']}/bills",
        data={"year": "2026", "month": "10", "taken_on": "2026-11-03"},
    )

    assert response.status_code == 422
    assert "Подать показания" in response.text
    assert "has no reading for 2026-10" in response.text
