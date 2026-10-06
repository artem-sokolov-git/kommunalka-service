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
    assert "Было 1\u00a0октября" in page


def test_without_unbilled_months_links_last_bill(
    client: TestClient, household: dict[str, Any]
) -> None:
    page = client.get(readings_url(household)).text

    assert "Ждёт выставления" not in page
    assert f"/view/households/{household['id']}/bills/2026/9" in page


def test_previews_the_bill_the_readings_close(
    client: TestClient, household: dict[str, Any]
) -> None:
    page = client.get(readings_url(household), params={"taken_on": "2026-11-03"}).text

    assert "Счёт за октябрь" in page
    assert 'data-price="7.96"' in page
    assert 'name="fixed_amount" inputmode="decimal" value="300,78"' in page
    assert "Сохранить и выставить счёт" in page


def test_saves_readings_and_issues_bill_at_once(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any]
) -> None:
    transport = next(s for s in client.get("/services").json() if not s["unit"])
    response = client.post(
        readings_url(household),
        data={
            "taken_on": "2026-11-03",
            "meter_id": [meter["id"]],
            "value": ["41800"],
            "action": "issue",
            "fixed_service_id": [transport["id"]],
            "fixed_amount": ["295,10"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        f"/view/households/{household['id']}/bills/2026/10?issued=1" in response.headers["location"]
    )
    assert "Счёт выставлен" in client.get(response.headers["location"]).text
    bill = client.get(f"/households/{household['id']}/bills/2026/10").json()
    assert {line["amount"] for line in bill["lines"]} == {"254.72", "295.10"}


def test_failed_bill_keeps_no_readings(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any]
) -> None:
    transport = next(s for s in client.get("/services").json() if not s["unit"])
    response = client.post(
        readings_url(household),
        data={
            "taken_on": "2026-11-03",
            "meter_id": [meter["id"]],
            "value": ["41800"],
            "action": "issue",
            "fixed_service_id": [transport["id"]],
            "fixed_amount": ["abc"],
        },
    )

    assert response.status_code == 422
    assert "не число «abc»" in response.text
    assert 'value="abc"' in response.text
    assert len(client.get(f"/meters/{meter['id']}/readings").json()) == 3


@pytest.mark.parametrize("opened_on", ["2026-11-03", "2026-12-31", "2027-02-01"])
def test_offers_bill_for_month_closed_by_readings(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any], opened_on: str
) -> None:
    submit(client, household, meter, "41800")

    page = client.get(readings_url(household), params={"taken_on": opened_on}).text

    assert "Выставить счёт за октябрь 2026" in page


def test_rejects_reading_from_the_future(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any]
) -> None:
    response = client.post(
        readings_url(household),
        data={"taken_on": "2027-01-01", "meter_id": [meter["id"]], "value": ["41800"]},
    )

    assert response.status_code == 422
    assert "Дата показания 01.01.2027 ещё не наступила" in response.text
    assert "Газовый: дата" not in response.text


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
    [
        ("41000", "Газовый: показание меньше предыдущего"),
        ("abc", "Газовый: не число «abc»"),
        ("", "хотя бы одно"),
    ],
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
        f"/view/households/{household['id']}/bills/2026/10?issued=1"
    )
    assert client.get(response.headers["location"]).status_code == 200


def test_bill_error_is_shown_on_the_readings_page(
    client: TestClient, household: dict[str, Any]
) -> None:
    response = client.post(
        f"/view/households/{household['id']}/bills",
        data={"year": "2026", "month": "10"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    page = client.get(response.headers["location"])
    assert page.url.path == readings_url(household)
    assert "Нет показания счётчика «Газовый» за октябрь 2026" in page.text


def test_date_cannot_be_picked_in_the_future(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(readings_url(household)).text

    assert 'max="2026-12-31"' in page


def test_names_the_month_of_the_last_bill(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(readings_url(household)).text

    assert "Последний счёт: сентябрь 2026" in page


@pytest.fixture
def november(client: TestClient, household: dict[str, Any], meter: dict[str, Any]) -> str:
    submit(client, household, meter, "41800")
    return client.get(f"/meters/{meter['id']}/readings").json()[-1]["id"]


def correction_url(household: dict[str, Any], reading_id: str) -> str:
    return f"/view/households/{household['id']}/readings/{reading_id}"


def test_no_correction_for_billed_month(client: TestClient, household: dict[str, Any]) -> None:
    page = client.get(readings_url(household)).text

    assert "исправить" not in page


def test_offers_correction_for_unbilled_month(
    client: TestClient, household: dict[str, Any], november: str
) -> None:
    page = client.get(readings_url(household)).text

    assert correction_url(household, november) in page


def test_corrects_reading(
    client: TestClient, household: dict[str, Any], meter: dict[str, Any], november: str
) -> None:
    page = client.get(correction_url(household, november)).text
    assert 'value="41\u00a0800"' in page
    assert "Предыдущее: 1\u00a0октября 2026" in page
    assert "41\u00a0768" in page

    response = client.post(
        correction_url(household, november), data={"value": "41 790"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert "Показание исправлено" in client.get(response.headers["location"]).text
    assert client.get(f"/meters/{meter['id']}/readings").json()[-1]["value"] == "41790"


def test_correction_error_is_shown(
    client: TestClient, household: dict[str, Any], november: str
) -> None:
    response = client.post(correction_url(household, november), data={"value": "41000"})

    assert response.status_code == 422
    assert "Показание меньше предыдущего" in response.text
    assert 'value="41000"' in response.text


def test_reading_of_another_household_is_404(client: TestClient, november: str) -> None:
    other = client.post("/households", json={"name": "Другой", "address": "ул. Другая 2"}).json()

    assert client.get(correction_url(other, november)).status_code == 404
    response = client.post(correction_url(other, november), data={"value": "1"})
    assert response.status_code == 404
