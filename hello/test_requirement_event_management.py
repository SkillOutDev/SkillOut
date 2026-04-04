import json
import sys
import types
from datetime import date, time
from decimal import Decimal

import pytest

from hello.models import Category, Event


POST_EVENT_ENDPOINT = "/api/events/add/"
LIST_EVENTS_ENDPOINT = "/api/events/"
PURGE_ENDPOINT = "/api/events/purge-ended/"


def _mock_ollama_module():
    return types.SimpleNamespace(
        chat=lambda **kwargs: {"message": {"content": "Sugeneruota rekomendacija."}}
    )


def _event_payload(**overrides):
    payload = {
        "name": "Koncertas",
        "date": "2026-04-05",
        "time": "19:00",
        "place": "Vilnius",
        "categories": ["Muzika"],
        "short_description": "Ilgas renginio aprasymas",
        "price": "12.50",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_purge_ended_events_removes_expired_events(client):
    Event.objects.create(
        name="Senas renginys",
        date=date(2020, 1, 1),
        time=time(10, 0),
        place="Vilnius",
        short_description="Jau pasibaiges renginys",
        price=Decimal("1.00"),
    )
    Event.objects.create(
        name="Ateities renginys",
        date=date(2030, 1, 1),
        time=time(10, 0),
        place="Vilnius",
        short_description="Dar nepasibaiges renginys",
        price=Decimal("1.00"),
    )

    response = client.delete(PURGE_ENDPOINT)

    assert response.status_code == 200
    assert Event.objects.filter(name="Senas renginys").count() == 0
    assert Event.objects.filter(name="Ateities renginys").count() == 1


@pytest.mark.django_db
def test_get_event_by_id_returns_existing_event(client, monkeypatch):
    event = Event.objects.create(
        id=1,
        name="Koncertas",
        date=date(2026, 4, 5),
        time=time(19, 0),
        place="Vilnius",
        short_description="Ilgas renginio aprasymas",
        price=Decimal("12.50"),
    )

    monkeypatch.setitem(sys.modules, "ollama", _mock_ollama_module())

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == 1
    assert body["name"] == "Koncertas"


@pytest.mark.django_db
def test_create_event_with_valid_payload(client):
    response = client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload()),
        content_type="application/json",
    )

    assert response.status_code == 201

    body = response.json()
    assert body["name"] == "Koncertas"
    assert body["date"] == "2026-04-05"
    assert body["time"] == "19:00"
    assert body["categories"] == ["Muzika"]
    assert body["short_description"] == "Ilgas renginio aprasymas"
    assert body["price"] == "12.50"

    created = Event.objects.get(name="Koncertas", date=date(2026, 4, 5))
    assert created.time == time(19, 0)


@pytest.mark.django_db
def test_create_event_when_unique_name_date_time_combination(client):
    assert Event.objects.filter(
        name="Koncertas",
        date=date(2026, 4, 5),
        time=time(19, 0),
    ).count() == 0

    response = client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload()),
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Event.objects.filter(
        name="Koncertas",
        date=date(2026, 4, 5),
        time=time(19, 0),
    ).count() == 1


@pytest.mark.django_db
def test_get_events_returns_all_events_with_required_fields(client):
    music = Category.objects.create(name="Muzika")
    art = Category.objects.create(name="Menas")

    event_1 = Event.objects.create(
        name="Koncertas",
        date=date(2026, 4, 5),
        time=time(19, 0),
        place="Vilnius",
        short_description="Ilgas renginio aprasymas",
        price=Decimal("12.50"),
    )
    event_1.categories.add(music)

    event_2 = Event.objects.create(
        name="Paroda",
        date=date(2026, 4, 10),
        time=time(10, 0),
        place="Kaunas",
        short_description="Moderniosios meno paroda",
        price=Decimal("5.00"),
    )
    event_2.categories.add(art)

    response = client.get(LIST_EVENTS_ENDPOINT)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["events"], list)
    assert len(body["events"]) == 2

    for item in body["events"]:
        assert "name" in item
        assert "date" in item
        assert "time" in item
        assert "categories" in item
        assert "short_description" in item
        assert "price" in item


@pytest.mark.django_db
def test_create_duplicate_event_returns_conflict_requirement(client):
    client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload()),
        content_type="application/json",
    )

    response = client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload()),
        content_type="application/json",
    )

    # Requirement expects 409 and no new event.
    # This test intentionally captures that business rule.
    assert response.status_code == 409
    assert Event.objects.filter(name="Koncertas", date=date(2026, 4, 5)).count() == 1


@pytest.mark.django_db
def test_get_events_returns_empty_array_when_no_events(client):
    response = client.get(LIST_EVENTS_ENDPOINT)

    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.django_db
def test_get_event_by_id_returns_404_for_missing_event(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", _mock_ollama_module())

    response = client.get("/api/events/999/")

    assert response.status_code == 404
    assert "error" in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,expected_error",
    [
        (
            _event_payload(name=""),
            "Event title must not be empty",
        ),
        (
            _event_payload(date="05-04"),
            "Event date must be in YYYY-MM-DD format",
        ),
        (
            _event_payload(time="7 PM"),
            "Event time must be in HH:mm format",
        ),
        (
            _event_payload(categories=[]),
            "Event must have at least one category",
        ),
        (
            _event_payload(short_description="apr"),
            "Event description must be at least 10 characters long",
        ),
        (
            _event_payload(price="12.345"),
            "Event price must be a decimal number with up to 2 decimal places",
        ),
    ],
)
def test_event_payload_validation_requirements(client, payload, expected_error):
    response = client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json().get("error") == expected_error
