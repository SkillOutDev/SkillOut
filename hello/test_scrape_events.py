import builtins
import json
import sys
import types
from unittest.mock import Mock

import pytest
import requests

from hello.models import Category, Event, EventPageUrl


ENDPOINT = "/api/scrape-events/"


def _post(client, payload):
    return client.post(ENDPOINT, data=json.dumps(payload), content_type="application/json")


def _ollama(content):
    return types.SimpleNamespace(
        chat=Mock(return_value={"message": {"content": content}})
    )


def _page_response(text):
    response = Mock()
    response.text = text
    response.raise_for_status.return_value = None
    return response


def _event(**overrides):
    result = {
        "name": "Renginys",
        "date": "2026-06-10",
        "time": "18:30",
        "place": "Vilnius",
        "price": "15.5",
        "categories": ["Muzika", "Gyvai"],
        "short_description": "Gyvas koncertas",
    }
    result.update(overrides)
    return result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,error",
    [
        ([], "Field 'url' is required."),
        ({"url": "   "}, "Field 'url' is required."),
        ({"url": "ftp://example.com"}, "URL must start with http:// or https://."),
        ({"url": "https://example.com", "max_events": "many"}, "max_events must be a number."),
        ({"url": "https://example.com", "max_events": 0}, "max_events must be at least 1."),
    ],
)
def test_scrape_events_rejects_invalid_request(client, payload, error):
    response = _post(client, payload)

    assert response.status_code == 400
    assert response.json() == {"error": error}


@pytest.mark.django_db
def test_scrape_events_reports_http_error(client, monkeypatch):
    error = requests.HTTPError("not found")
    error.response = types.SimpleNamespace(status_code=404)
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(side_effect=error))

    response = _post(client, {"url": "https://example.com"})

    assert response.status_code == 400
    assert response.json() == {"error": "HTTP error: 404"}


@pytest.mark.django_db
def test_scrape_events_retries_timeouts_then_returns_error(client, monkeypatch):
    get = Mock(side_effect=requests.Timeout("timed out"))
    sleep = Mock()
    monkeypatch.setattr("hello.services.event_scraping.requests.get", get)
    monkeypatch.setattr("hello.services.event_scraping.time.sleep", sleep)

    response = _post(client, {"url": "https://example.com"})

    assert response.status_code == 400
    assert response.json()["error"] == "Failed after 3 attempts: timed out"
    assert get.call_count == 3
    assert sleep.call_count == 2


@pytest.mark.django_db
def test_scrape_events_retries_timeout_then_continues(client, monkeypatch):
    get = Mock(
        side_effect=[
            requests.Timeout("temporary timeout"),
            _page_response("<p>Renginiai</p>"),
        ]
    )
    sleep = Mock()
    monkeypatch.setattr("hello.services.event_scraping.requests.get", get)
    monkeypatch.setattr("hello.services.event_scraping.time.sleep", sleep)
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Puslapio tekstas"))
    monkeypatch.setitem(sys.modules, "ollama", _ollama(json.dumps({"events": []})))
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(client, {"url": "https://example.com"})

    assert response.status_code == 200
    assert get.call_count == 2
    sleep.assert_called_once_with(1)


@pytest.mark.django_db
def test_scrape_events_reports_other_request_exception(client, monkeypatch):
    monkeypatch.setattr(
        "hello.services.event_scraping.requests.get",
        Mock(side_effect=requests.RequestException("bad request")),
    )

    response = _post(client, {"url": "https://example.com"})

    assert response.status_code == 400
    assert response.json() == {"error": "Request failed: bad request"}


@pytest.mark.django_db
def test_scrape_events_reports_missing_ollama_package(client, monkeypatch):
    original_import = builtins.__import__

    def import_without_ollama(name, *args, **kwargs):
        if name == "ollama":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_ollama)
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(return_value=_page_response("<p>Renginiai</p>")))

    response = _post(client, {"url": "https://example.com"})

    assert response.status_code == 500
    assert response.json() == {
        "error": "Ollama Python package is not installed. Install it with: pip install ollama"
    }


@pytest.mark.django_db
def test_scrape_events_reports_ollama_and_invalid_json_failures(client, monkeypatch):
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(return_value=_page_response("<p>Renginiai</p>")))
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Renginio aprašymas"))
    monkeypatch.setitem(sys.modules, "ollama", _ollama("ne JSON"))
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    monkeypatch.setitem(
        sys.modules,
        "ollama",
        types.SimpleNamespace(chat=Mock(side_effect=RuntimeError("model unavailable"))),
    )
    failed_response = _post(client, {"url": "https://example.com"})
    assert failed_response.status_code == 500
    assert failed_response.json() == {"error": "Ollama request failed: model unavailable"}

    monkeypatch.setitem(sys.modules, "ollama", _ollama("not JSON"))
    invalid_response = _post(client, {"url": "https://example.com"})
    assert invalid_response.status_code == 500
    assert invalid_response.json() == {"error": "Could not parse events JSON from model output."}


@pytest.mark.django_db
def test_scrape_events_extracts_and_saves_events_for_generic_source(client, monkeypatch):
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(return_value=_page_response("<p>Renginiai</p>")))
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Puslapio tekstas"))
    monkeypatch.setitem(
        sys.modules,
        "ollama",
        _ollama(
            json.dumps(
                {
                    "events": [
                        _event(),
                        "not an event",
                        _event(name="", date="bad"),
                        _event(name="Be laiko", time=None, categories=["", "  "]),
                        _event(name="Be vietos", place=""),
                    ]
                }
            )
        ),
    )
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(
        client,
        {"url": "https://example.com/events", "model": "  llama-test  ", "max_events": "5"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_events"] == 2
    assert body["updated_events"] == 0
    assert body["failed_count"] == 2
    assert body["events"][0]["time"] == "18:30"
    assert body["events"][0]["price"] == "15.50"
    assert body["events"][1]["time"] == "00:00"
    assert body["events"][1]["categories"] == []
    assert body["failed"][0]["error"] == "Missing or invalid required fields (name, date, time, place, price)."
    assert body["failed"][1]["error"] == "Missing or invalid required fields (name, date, time, place, price)."
    event = Event.objects.get(name="Renginys")
    assert event.source_url == ""
    assert set(event.categories.values_list("name", flat=True)) == {"Muzika", "Gyvai"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,listing_html,detail_url,expected_source,city",
    [
        (
            "https://www.litexpo.lt/en/events",
            '<a href="/en/events/conference/">Event</a>',
            "https://www.litexpo.lt/en/events/conference/",
            "litexpo",
            "",
        ),
        (
            "https://www.meetup.com/find/events/?region=eu&location=Vilnius--Lithuania",
            '<a href="/vilnius/events/123/">Event</a>',
            "https://www.meetup.com/vilnius/events/123/",
            "meetup",
            "Lithuania",
        ),
        (
            "https://kaveikti.lt/renginiai",
            '<a href="/renginiai/koncertas/">Event</a>',
            "https://kaveikti.lt/renginiai/koncertas/",
            "kaveikti",
            "",
        ),
    ],
)
def test_scrape_events_handles_supported_sources(
    client, monkeypatch, url, listing_html, detail_url, expected_source, city
):
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(return_value=_page_response(listing_html)))
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Renginio detalės"))
    event_place = "Kaunas" if expected_source == "kaveikti" else ""
    chat = _ollama(json.dumps(_event(place=event_place)))
    monkeypatch.setitem(sys.modules, "ollama", chat)
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(client, {"url": url})

    assert response.status_code == 200
    assert response.json()["created_events"] == 1
    assert response.json()["events"][0]["source_url"] == detail_url
    assert EventPageUrl.objects.get(url=detail_url).source == expected_source
    assert EventPageUrl.objects.get(url=detail_url).city == city
    assert chat.chat.call_args.kwargs["model"] == "llama3"
    if expected_source == "meetup":
        assert response.json()["events"][0]["place"] == "Lithuania"


@pytest.mark.django_db
def test_scrape_events_uses_saved_links_and_records_detail_failures(client, monkeypatch):
    detail_url = "https://www.litexpo.lt/en/events/saved-event/"
    EventPageUrl.objects.create(url=detail_url, source="litexpo", city="Kaunas")
    monkeypatch.setattr(
        "hello.services.event_scraping.requests.get",
        Mock(return_value=_page_response("<p>No links</p>")),
    )
    monkeypatch.setattr(
        "hello.services.event_scraping._get_clean_page_text",
        Mock(side_effect=[requests.ConnectionError("page unavailable")]),
    )
    monkeypatch.setitem(sys.modules, "ollama", _ollama("{}"))
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(
        client,
        {"url": "https://www.litexpo.lt/en/events", "city": "Kaunas"},
    )

    assert response.status_code == 200
    assert response.json()["failed"] == [
        {"source_url": detail_url, "error": "Failed to open detail page: page unavailable"}
    ]
    assert response.json()["failed_count"] == 1


@pytest.mark.django_db
def test_scrape_events_returns_error_when_supported_source_has_no_event_links(client, monkeypatch):
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(return_value=_page_response("<p>No links</p>")))
    monkeypatch.setitem(sys.modules, "ollama", _ollama("{}"))

    response = _post(client, {"url": "https://www.litexpo.lt/en/events"})

    assert response.status_code == 400
    assert response.json() == {
        "error": "No event links found for source 'litexpo' and no saved links are available."
    }


@pytest.mark.django_db
def test_scrape_events_updates_existing_event_and_handles_detail_model_failures(client, monkeypatch):
    Event.objects.create(
        name="Renginys",
        date="2026-06-10",
        time="12:00",
        place="Senas miestas",
        price="1.00",
        short_description="Senas aprašymas",
    )
    first_url = "https://www.litexpo.lt/en/events/first/"
    second_url = "https://www.litexpo.lt/en/events/second/"
    listing = f'<a href="{first_url}">one</a><a href="{second_url}">two</a>'
    monkeypatch.setattr("hello.services.event_scraping.requests.get", Mock(return_value=_page_response(listing)))
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Detalės"))
    monkeypatch.setitem(
        sys.modules,
        "ollama",
        types.SimpleNamespace(
            chat=Mock(
                side_effect=[
                    {"message": {"content": json.dumps(_event(categories=[]))}},
                    {"message": {"content": "not json"}},
                ]
            )
        ),
    )
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(client, {"url": "https://www.litexpo.lt/en/events"})

    assert response.status_code == 200
    assert response.json()["updated_events"] == 1
    assert response.json()["failed_count"] == 1
    assert response.json()["failed"][0]["error"] == "Could not parse model JSON output."
    event = Event.objects.get(name="Renginys")
    assert event.place == "Vilnius"
    assert str(event.price) == "15.50"
    assert Category.objects.count() == 0


@pytest.mark.django_db
def test_scrape_events_handles_detail_ollama_failure_and_meetup_location_payload(client, monkeypatch):
    detail_url = "https://www.meetup.com/group/events/123/"
    monkeypatch.setattr(
        "hello.services.event_scraping.requests.get",
        Mock(return_value=_page_response(f'<a href="{detail_url}">Event</a>')),
    )
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Detalės"))
    ollama = types.SimpleNamespace(chat=Mock(side_effect=RuntimeError("down")))
    monkeypatch.setitem(sys.modules, "ollama", ollama)
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(
        client,
        {
            "url": "https://www.meetup.com/find/events/",
            "location": "Country--Kaunas",
            "city": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["failed"][0]["error"] == "Ollama request failed: down"
    assert "City hint: Kaunas" in ollama.chat.call_args.kwargs["messages"][0]["content"]


@pytest.mark.django_db
def test_scrape_events_uses_vilnius_page_text_as_meetup_city(client, monkeypatch):
    detail_url = "https://www.meetup.com/group/events/456/"
    monkeypatch.setattr(
        "hello.services.event_scraping.requests.get",
        Mock(return_value=_page_response(f"Vilnius <a href='{detail_url}'>Event</a>")),
    )
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Detalės"))
    monkeypatch.setitem(sys.modules, "ollama", _ollama(json.dumps(_event(place=""))))
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(client, {"url": "https://www.meetup.com/find/events/"})

    assert response.status_code == 200
    assert response.json()["events"][0]["place"] == "Vilnius"
    assert EventPageUrl.objects.get(url=detail_url).city == "Vilnius"


@pytest.mark.django_db
def test_scrape_events_preserves_explicit_meetup_city(client, monkeypatch):
    detail_url = "https://www.meetup.com/group/events/789/"
    monkeypatch.setattr(
        "hello.services.event_scraping.requests.get",
        Mock(return_value=_page_response(f'<a href="{detail_url}">Event</a>')),
    )
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Detalės"))
    monkeypatch.setitem(sys.modules, "ollama", _ollama(json.dumps(_event(place=""))))
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(
        client,
        {
            "url": "https://www.meetup.com/find/events/?location=Vilnius--Lithuania",
            "city": "Kaunas",
        },
    )

    assert response.status_code == 200
    assert response.json()["events"][0]["place"] == "Kaunas"
    assert EventPageUrl.objects.get(url=detail_url).city == "Kaunas"


@pytest.mark.django_db
def test_scrape_events_keeps_empty_meetup_city_when_no_location_is_available(client, monkeypatch):
    detail_url = "https://www.meetup.com/group/events/101/"
    monkeypatch.setattr(
        "hello.services.event_scraping.requests.get",
        Mock(return_value=_page_response(f'<a href="{detail_url}">Event</a>')),
    )
    monkeypatch.setattr("hello.services.event_scraping._get_clean_page_text", Mock(return_value="Details"))
    monkeypatch.setitem(sys.modules, "ollama", _ollama(json.dumps(_event(place="Kaunas"))))
    monkeypatch.setattr("hello.services.event_scraping.Path.mkdir", Mock())
    monkeypatch.setattr("hello.services.event_scraping.Path.write_text", Mock())

    response = _post(client, {"url": "https://www.meetup.com/find/events/"})

    assert response.status_code == 200
    assert EventPageUrl.objects.get(url=detail_url).city == ""


def test_scrape_events_supports_additional_registered_source(monkeypatch):
    from bs4 import BeautifulSoup
    from hello.services import event_scraping

    custom_strategy = event_scraping.EventSourceStrategy(
        name="custom",
        matches=lambda host, path, query, page_text: host == "events.example",
        extract_links=lambda soup, url, max_events: ["https://events.example/event/1"],
        build_prompt=lambda detail_url, detail_text, city: "custom prompt",
    )
    monkeypatch.setattr(event_scraping, "EVENT_SOURCE_STRATEGIES", (custom_strategy,))
    request_data = event_scraping._prepare_scrape_events_request(
        {"url": "https://events.example/calendar", "max_events": 3}
    )

    strategy, city, links = event_scraping._discover_event_source(
        request_data.url,
        BeautifulSoup("<p>Events</p>", "html.parser"),
        request_data,
    )

    assert strategy is custom_strategy
    assert city == ""
    assert links == ["https://events.example/event/1"]


def test_scrape_events_json_writer_preserves_output_structure(tmp_path):
    from hello.services.event_scraping import SavedScrapedEvents, _write_scraped_events_json

    results = SavedScrapedEvents(
        created_count=1,
        updated_count=0,
        events=[{"name": "Renginys"}],
        failed=[{"name": "Kitas", "error": "invalid"}],
    )

    output_file = _write_scraped_events_json(
        tmp_path,
        "https://example.com",
        "other",
        "Vilnius",
        results,
    )

    assert json.loads(output_file.read_text(encoding="utf-8")) == {
        "url": "https://example.com",
        "source": "other",
        "city": "Vilnius",
        "events": [{"name": "Renginys"}],
        "failed": [{"name": "Kitas", "error": "invalid"}],
    }


@pytest.mark.parametrize(
    "extractor,base_url,html,expected",
    [
        (
            "_extract_litexpo_event_links",
            "https://www.litexpo.lt/en/events/",
            '<a href="/en/events/">index</a>'
            '<a href="/en/events/first/?ref=one">first</a>'
            '<a href="/en/events/first/#info">duplicate</a>'
            '<a href="https://other.example/en/events/other/">other</a>'
            '<a href="/en/events/second/">second</a>',
            [
                "https://www.litexpo.lt/en/events/first/",
                "https://www.litexpo.lt/en/events/second/",
            ],
        ),
        (
            "_extract_meetup_event_links",
            "https://www.meetup.com/find/events/",
            '<a href="/find/events/">find</a>'
            '<a href="/topics/events/">topics</a>'
            '<a href="/group/events/123?ref=one">first</a>'
            '<a href="/group/events/123/#info">duplicate</a>'
            '<a href="https://other.example/group/events/999/">other</a>'
            '<a href="/group/events/456/">second</a>',
            [
                "https://www.meetup.com/group/events/123/",
                "https://www.meetup.com/group/events/456/",
            ],
        ),
        (
            "_extract_kaveikti_event_links",
            "https://kaveikti.lt/renginiai/",
            '<a href="/renginiai/">index</a>'
            '<a href="/renginiai/first?ref=one">first</a>'
            '<a href="/renginiai/first/#info">duplicate</a>'
            '<a href="https://other.example/renginiai/other/">other</a>'
            '<a href="/renginiai/second/">second</a>',
            [
                "https://kaveikti.lt/renginiai/first/",
                "https://kaveikti.lt/renginiai/second/",
            ],
        ),
    ],
)
def test_event_link_extractors_filter_normalize_and_limit(extractor, base_url, html, expected):
    from bs4 import BeautifulSoup
    from hello.services import event_scraping

    extract = getattr(event_scraping, extractor)
    assert extract(BeautifulSoup(html, "html.parser"), base_url, 1) == expected[:1]
    assert extract(BeautifulSoup(html, "html.parser"), base_url, 10) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"name": "Concert"}', {"name": "Concert"}),
        ('```json\n{"name": "Concert"}\n```', {"name": "Concert"}),
        ('Here is the event: {"name": "Concert"}', {"name": "Concert"}),
        ("text {invalid}", None),
        ("not json", None),
    ],
)
def test_parse_json_from_model_output(raw, expected):
    from hello.services.event_scraping import _parse_json_from_model_output

    assert _parse_json_from_model_output(raw) == expected


def test_get_clean_page_text_removes_noncontent_elements(monkeypatch):
    from hello.services.event_scraping import _get_clean_page_text

    get = Mock(return_value=_page_response(
        "<h1>Concert</h1><script>hidden</script><style>hidden</style>"
        "<noscript>hidden</noscript><p>Vilnius</p>"
    ))
    monkeypatch.setattr("hello.services.event_scraping.requests.get", get)

    assert _get_clean_page_text("https://example.com/event", timeout=4) == "Concert Vilnius"
    get.assert_called_once_with("https://example.com/event", timeout=4)
