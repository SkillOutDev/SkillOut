import json
import sys
import types

import pytest

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
    client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(
            _event_payload(
                name="Senas renginys",
                date="2020-01-01",
                time="10:00",
                short_description="Jau pasibaiges renginys",
                price="1.00",
            )
        ),
        content_type="application/json",
    )
    client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(
            _event_payload(
                name="Ateities renginys",
                date="2030-01-01",
                time="10:00",
                short_description="Dar nepasibaiges renginys",
                price="1.00",
            )
        ),
        content_type="application/json",
    )

    response = client.delete(PURGE_ENDPOINT)

    assert response.status_code == 200
    list_response = client.get(LIST_EVENTS_ENDPOINT)
    names = [event["name"] for event in list_response.json()["events"]]
    assert "Senas renginys" not in names
    assert "Ateities renginys" in names


@pytest.mark.django_db
def test_get_event_by_id_returns_existing_event(client, monkeypatch):
    create_response = client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload()),
        content_type="application/json",
    )
    event_id = create_response.json()["event_id"]

    monkeypatch.setitem(sys.modules, "ollama", _mock_ollama_module())

    response = client.get(f"/api/events/{event_id}/")

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == event_id
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


@pytest.mark.django_db
def test_create_event_when_unique_name_date_time_combination(client):
    response = client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload()),
        content_type="application/json",
    )

    assert response.status_code == 201
    list_response = client.get(LIST_EVENTS_ENDPOINT)
    events = list_response.json()["events"]
    assert any(
        event["name"] == "Koncertas"
        and event["date"] == "2026-04-05"
        and event["time"] == "19:00"
        for event in events
    )


@pytest.mark.django_db
def test_get_events_returns_all_events_with_required_fields(client):
    client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(_event_payload(name="Koncertas", categories=["Muzika"])),
        content_type="application/json",
    )
    client.post(
        POST_EVENT_ENDPOINT,
        data=json.dumps(
            _event_payload(
                name="Paroda",
                date="2026-04-10",
                time="10:00",
                place="Kaunas",
                short_description="Moderniosios meno paroda",
                price="5.00",
                categories=["Menas"],
            )
        ),
        content_type="application/json",
    )

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
    list_response = client.get(LIST_EVENTS_ENDPOINT)
    duplicates = [
        event
        for event in list_response.json()["events"]
        if event["name"] == "Koncertas" and event["date"] == "2026-04-05"
    ]
    assert len(duplicates) == 1


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
