import json

import pytest

from hello.models import Category, Event


ENDPOINT = "/api/events/add/"


def _payload(**overrides):
    payload = {
        "name": "Koncertas",
        "date": "2026-04-05",
        "time": "19:00",
        "place": "Vilnius",
        "price": "12.50",
        "short_description": "Gyvos muzikos vakaras",
        "categories": ["Muzika"],
        "source_url": "https://example.com/events/koncertas",
    }
    payload.update(overrides)
    return payload


def _post(client, payload):
    return client.post(ENDPOINT, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_add_event_creates_event_with_categories_and_source_url(client):
    response = _post(client, _payload(categories=[" Muzika ", "", "Koncertai "]))

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "message": "Event created.",
        "event_id": body["event_id"],
        "name": "Koncertas",
        "date": "2026-04-05",
        "time": "19:00",
        "place": "Vilnius",
        "price": "12.50",
        "short_description": "Gyvos muzikos vakaras",
        "categories": ["Muzika", "Koncertai"],
        "source_url": "https://example.com/events/koncertas",
        "created": True,
    }
    event = Event.objects.get(pk=body["event_id"])
    assert list(event.categories.values_list("name", flat=True)) == ["Muzika", "Koncertai"]
    assert Category.objects.count() == 2


@pytest.mark.django_db
def test_add_event_trims_text_and_applies_optional_defaults(client):
    response = _post(
        client,
        _payload(
            name="  Paroda  ",
            time=None,
            place="  Kaunas ",
            price=" free ",
            short_description="  ",
            categories=[],
            source_url="  ",
        ),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Paroda"
    assert response.json()["time"] == "00:00"
    assert response.json()["place"] == "Kaunas"
    assert response.json()["price"] == "0.00"
    assert response.json()["short_description"] == ""
    assert response.json()["categories"] == []
    assert response.json()["source_url"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "Event title must not be empty"),
        ({"name": "Renginys"}, "'date' is required (YYYY-MM-DD)."),
        ({"name": "Renginys", "date": "2026-04-05"}, "'place' is required."),
        (_payload(date="05-04-2026"), "Event date must be in YYYY-MM-DD format"),
        (_payload(date="2026-02-30"), "Event date must be in YYYY-MM-DD format"),
        (_payload(time="7 PM"), "Event time must be in HH:mm format"),
        (_payload(price="abc"), "Event price must be a decimal number with up to 2 decimal places"),
        (_payload(price="12.345"), "Event price must be a decimal number with up to 2 decimal places"),
        (_payload(price="12345678901"), "Event price must be a decimal number with up to 2 decimal places"),
        (_payload(price="NaN"), "Event price must be a decimal number with up to 2 decimal places"),
        (_payload(categories="Muzika"), "'categories' must be a list of strings."),
        (_payload(categories=["Muzika", 3]), "'categories' must be a list of strings."),
    ],
)
def test_add_event_rejects_invalid_payload(client, payload, error):
    response = _post(client, payload)

    assert response.status_code == 400
    assert response.json() == {"error": error}
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_add_event_rejects_duplicate_name_date_and_time(client):
    assert _post(client, _payload()).status_code == 201

    response = _post(client, _payload(price="99.00"))

    assert response.status_code == 409
    assert response.json() == {"error": "Event already exists."}
    assert Event.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("price", ["", "free", "1 234,5 EUR", "€8"])
def test_add_event_accepts_supported_price_formats(client, price):
    response = _post(client, _payload(price=price))

    assert response.status_code == 201
    assert response.json()["price"] == {
        "": "0.00",
        "free": "0.00",
        "1 234,5 EUR": "1234.50",
        "€8": "8.00",
    }[price]


@pytest.mark.django_db
def test_add_event_rejects_price_when_price_parser_cannot_parse_it(client, monkeypatch):
    monkeypatch.setattr("hello.views._parse_event_price", lambda value: None)

    response = _post(client, _payload())

    assert response.status_code == 400
    assert response.json() == {
        "error": "Event price must be a decimal number with up to 2 decimal places"
    }
