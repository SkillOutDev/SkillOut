import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import ParseResult, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone

from ..models import Category, Event, EventPageUrl
from .event_creation import _parse_event_date, _parse_event_price, _parse_event_time


def _extract_litexpo_event_links(soup, base_url, max_events=20):
    links = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") + "/"

        if "/en/events/" not in parsed.path:
            continue
        if normalized.endswith("/en/events/"):
            continue
        if parsed.netloc != "www.litexpo.lt":
            continue
        if normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

        if len(links) >= max_events:
            break

    return links


def _extract_meetup_event_links(soup, base_url, max_events=20):
    links = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") + "/"

        if parsed.netloc not in {"www.meetup.com", "meetup.com"}:
            continue
        if "/events/" not in parsed.path:
            continue
        if "/find/" in parsed.path or "/topics/" in parsed.path:
            continue
        if normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

        if len(links) >= max_events:
            break

    return links


def _extract_kaveikti_event_links(soup, base_url, max_events=20):
    links = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") + "/"

        if parsed.netloc not in {"www.kaveikti.lt", "kaveikti.lt"}:
            continue
        if "/renginiai/" in parsed.path and normalized.endswith("/renginiai/"):
            continue
        if "rengin" not in parsed.path.lower():
            continue
        if normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

        if len(links) >= max_events:
            break

    return links


def _build_litexpo_event_prompt(detail_url, detail_text, city):
    return (
        "Extract ONE event from this Litexpo detail page text and return strict JSON only. "
        "Output format: "
        '{"name": "", "date": "YYYY-MM-DD", "time": "HH:MM", "place": "", "price": "", '
        '"categories": [""], "short_description": ""}. '
        "Generate categories as topical tags based on the event content from the source page "
        "(examples: IT, Databases, Biology, Business, Engineering, Construction, Automotive, Art, Gaming). "
        "Use 2-5 concise categories and avoid generic values like 'Events' or 'Other'. "
        "If price is not provided, use 0. If place is not explicit, use 'LITEXPO, Vilnius'. "
        "If time is missing, use 00:00. Do not include markdown or explanation.\n\n"
        f"Source URL: {detail_url}\n"
        f"Detail page text:\n{detail_text}"
    )


def _build_meetup_event_prompt(detail_url, detail_text, city):
    city_hint = city or "Vilnius"
    return (
        "Extract ONE event from this Meetup event page text and return strict JSON only. "
        "Output format: "
        '{"name": "", "date": "YYYY-MM-DD", "time": "HH:MM", "place": "", "price": "", '
        '"categories": [""], "short_description": ""}. '
        "Use event location if available, otherwise use city hint. "
        "If event is free, set price to 0. If time is missing, use 00:00. "
        "Generate a short_description in 1 sentence based on event topic. "
        "Do not include markdown or explanation.\n\n"
        f"City hint: {city_hint}\n"
        f"Source URL: {detail_url}\n"
        f"Detail page text:\n{detail_text}"
    )


def _build_kaveikti_event_prompt(detail_url, detail_text, city):
    return (
        "Extract ONE event from this kaveikti.lt event page text and return strict JSON only. "
        "Output format: "
        '{"name": "", "date": "YYYY-MM-DD", "time": "HH:MM", "place": "", "price": "", '
        '"categories": [""], "short_description": ""}. '
        "For categories, infer broad tags like Music, Business, Tech, Education, Family, Sports. "
        "If price is unavailable, set 0. If time is missing, use 00:00. "
        "Generate short_description from event context. "
        "Do not include markdown or explanation.\n\n"
        f"Source URL: {detail_url}\n"
        f"Detail page text:\n{detail_text}"
    )


def _build_generic_event_prompt(text):
    return (
        "Extract events from the webpage text and return strict JSON only. "
        "Output format: "
        '{"events": [{"name": "", "date": "YYYY-MM-DD", "time": "HH:MM", "place": "", "price": "", '
        '"categories": [""], "short_description": ""}]}. '
        "If price is not provided, use 0. If time is missing, use 00:00. "
        "Do not include markdown or extra explanation.\n\n"
        f"Webpage text:\n{text}"
    )


def _save_discovered_event_urls(links, source, city=""):
    for link in links:
        EventPageUrl.objects.update_or_create(
            url=link,
            defaults={
                "source": source,
                "city": city or "",
                "is_active": True,
            },
        )


def _load_saved_event_urls(source, city="", max_events=20):
    qs = EventPageUrl.objects.filter(source=source, is_active=True)
    if city:
        qs = qs.filter(city__iexact=city)
    return list(qs.order_by("-last_seen").values_list("url", flat=True)[:max_events])


def _get_clean_page_text(url, timeout=10):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.extract()

    return soup.get_text(separator=" ", strip=True)[:60000]


def _parse_json_from_model_output(raw_content):
    raw_content = raw_content.strip()
    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw_content[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


@dataclass(frozen=True)
class ScrapeEventsRequest:
    url: str
    model_name: str
    max_events: int
    city: str
    location: object


class ScrapeEventsRequestError(ValueError):
    pass


class GenericEventModelError(Exception):
    pass


@dataclass(frozen=True)
class EventSourceStrategy:
    name: str
    matches: Callable[[str, str, str, str], bool]
    extract_links: Callable[[BeautifulSoup, str, int], list[str]]
    build_prompt: Callable[[str, str, str], str]
    resolve_city: Callable[[str, object, ParseResult, str], str] | None = None
    default_place: Callable[[str], str] | None = None


@dataclass
class SavedScrapedEvents:
    created_count: int
    updated_count: int
    events: list[dict]
    failed: list[dict]


def _prepare_scrape_events_request(data):
    payload = data if isinstance(data, dict) else {}
    url = (payload.get("url") or "").strip()
    model_name = (payload.get("model") or "llama3").strip()
    max_events = payload.get("max_events", 20)
    city = (payload.get("city") or "").strip()

    try:
        max_events = int(max_events)
    except (TypeError, ValueError) as exc:
        raise ScrapeEventsRequestError("max_events must be a number.") from exc
    if max_events < 1:
        raise ScrapeEventsRequestError("max_events must be at least 1.")
    if not url:
        raise ScrapeEventsRequestError("Field 'url' is required.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ScrapeEventsRequestError("URL must start with http:// or https://.")

    return ScrapeEventsRequest(
        url=url,
        model_name=model_name,
        max_events=max_events,
        city=city,
        location=payload.get("location") or "",
    )


def _fetch_scrape_events_page(url):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            raise ScrapeEventsRequestError(f"HTTP error: {exc.response.status_code}") from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == max_retries - 1:
                raise ScrapeEventsRequestError(
                    f"Failed after {max_retries} attempts: {exc}"
                ) from exc
            time.sleep(1)
        except requests.RequestException as exc:
            raise ScrapeEventsRequestError(f"Request failed: {exc}") from exc


def _matches_litexpo(host, path, query, page_text):
    return "litexpo.lt" in host and "/en/events" in path


def _matches_meetup(host, path, query, page_text):
    return "meetup.com" in host and (
        "/find/" in path
        or "/events/" in path
        or "vilnius" in query
        or "vilnius" in page_text
        or "events" in page_text
    )


def _matches_kaveikti(host, path, query, page_text):
    return "kaveikti.lt" in host and "/renginiai" in path


def _resolve_meetup_city(city, location, parsed_url, page_text):
    if not city:
        if location:
            city = str(location).split("--")[-1]
        elif "location=" in parsed_url.query:
            for part in parsed_url.query.split("&"):
                if part.startswith("location="):
                    city = part.split("=", 1)[-1].split("--")[-1]
                    break
        elif "vilnius" in parsed_url.query.lower() or "vilnius" in page_text:
            city = "Vilnius"
    return city


def _litexpo_default_place(city):
    return "LITEXPO, Vilnius"


def _meetup_default_place(city):
    return city


EVENT_SOURCE_STRATEGIES = (
    EventSourceStrategy(
        name="litexpo",
        matches=_matches_litexpo,
        extract_links=_extract_litexpo_event_links,
        build_prompt=_build_litexpo_event_prompt,
        default_place=_litexpo_default_place,
    ),
    EventSourceStrategy(
        name="meetup",
        matches=_matches_meetup,
        extract_links=_extract_meetup_event_links,
        build_prompt=_build_meetup_event_prompt,
        resolve_city=_resolve_meetup_city,
        default_place=_meetup_default_place,
    ),
    EventSourceStrategy(
        name="kaveikti",
        matches=_matches_kaveikti,
        extract_links=_extract_kaveikti_event_links,
        build_prompt=_build_kaveikti_event_prompt,
    ),
)


def _discover_event_source(url, soup, request_data):
    parsed_url = urlparse(url)
    host = parsed_url.netloc.lower()
    path = parsed_url.path.lower()
    query = parsed_url.query.lower()
    page_text = soup.get_text(" ", strip=True).lower()
    city = request_data.city

    for strategy in EVENT_SOURCE_STRATEGIES:
        if not strategy.matches(host, path, query, page_text):
            continue
        if strategy.resolve_city:
            city = strategy.resolve_city(
                city,
                request_data.location,
                parsed_url,
                page_text,
            )
        links = strategy.extract_links(
            soup,
            url,
            request_data.max_events,
        )
        return strategy, city, links

    return None, city, []


def _scrape_source_events(strategy, event_links, city, model_name, ollama):
    parsed_events = []
    failed_events = []

    for detail_url in event_links:
        try:
            detail_text = _get_clean_page_text(detail_url)
        except Exception as exc:
            failed_events.append(
                {"source_url": detail_url, "error": f"Failed to open detail page: {exc}"}
            )
            continue

        prompt = strategy.build_prompt(detail_url, detail_text, city)
        try:
            ollama_response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            failed_events.append(
                {"source_url": detail_url, "error": f"Ollama request failed: {exc}"}
            )
            continue

        model_payload = _parse_json_from_model_output(
            ollama_response.get("message", {}).get("content", "")
        )
        if not isinstance(model_payload, dict):
            failed_events.append(
                {"source_url": detail_url, "error": "Could not parse model JSON output."}
            )
            continue

        model_payload["source_url"] = detail_url
        parsed_events.append(model_payload)
        EventPageUrl.objects.filter(url=detail_url).update(last_scraped=timezone.now())

    return parsed_events, failed_events


def _scrape_generic_events(url, model_name, ollama):
    text = _get_clean_page_text(url)
    prompt = _build_generic_event_prompt(text)
    try:
        ollama_response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise GenericEventModelError(f"Ollama request failed: {exc}") from exc

    return _parse_json_from_model_output(
        ollama_response.get("message", {}).get("content", "")
    )


def _save_scraped_events(parsed_events, city, initial_failures, strategy=None):
    created_count = 0
    updated_count = 0
    saved_events = []
    failed_events = list(initial_failures)

    for item in parsed_events:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        date_value = _parse_event_date(item.get("date"))
        time_value = _parse_event_time(item.get("time"))
        place = str(item.get("place", "")).strip()
        price_value = _parse_event_price(item.get("price"))
        short_description = str(item.get("short_description", "")).strip()
        categories = item.get("categories") if isinstance(item.get("categories"), list) else []

        if not time_value:
            time_value = datetime.strptime("00:00", "%H:%M").time()
        if not place:
            place = strategy.default_place(city) if strategy and strategy.default_place else ""

        if not name or not date_value or not place or price_value is None:
            failed_events.append(
                {
                    "name": name,
                    "error": "Missing or invalid required fields (name, date, time, place, price).",
                    "raw": item,
                }
            )
            continue

        event, created = Event.objects.update_or_create(
            name=name,
            date=date_value,
            defaults={
                "time": time_value,
                "place": place,
                "price": price_value,
                "short_description": short_description or f"Event: {name}",
                "source_url": item.get("source_url") or "",
            },
        )

        event_categories = []
        for category_name in categories:
            category_name = str(category_name).strip()
            if not category_name:
                continue
            category, _ = Category.objects.get_or_create(name=category_name)
            event_categories.append(category)

        if event_categories:
            event.categories.set(event_categories)

        if created:
            created_count += 1
        else:
            updated_count += 1

        saved_events.append(
            {
                "event_id": event.id,
                "name": event.name,
                "date": str(event.date),
                "time": event.time.strftime("%H:%M"),
                "place": event.place,
                "price": str(event.price),
                "categories": [category.name for category in event.categories.all()],
                "short_description": event.short_description,
                "source_url": event.source_url,
            }
        )

    return SavedScrapedEvents(
        created_count=created_count,
        updated_count=updated_count,
        events=saved_events,
        failed=failed_events,
    )


def _write_scraped_events_json(output_dir, url, source, city, results):
    output_file = output_dir / "latest_events.json"
    output_file.write_text(
        json.dumps(
            {
                "url": url,
                "source": source,
                "city": city,
                "events": results.events,
                "failed": results.failed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_file



class OllamaUnavailableError(Exception):
    pass


class NoEventLinksError(ScrapeEventsRequestError):
    pass


@dataclass(frozen=True)
class ScrapeEventsResult:
    json_output_file: Path
    created_count: int
    updated_count: int
    events: list[dict]
    failed: list[dict]


def scrape_event_page(data):
    scrape_request = _prepare_scrape_events_request(data)
    response = _fetch_scrape_events_page(scrape_request.url)
    soup = BeautifulSoup(response.text, "html.parser")

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import ollama
    except ImportError as exc:
        raise OllamaUnavailableError(
            "Ollama Python package is not installed. Install it with: pip install ollama"
        ) from exc

    strategy, city, event_links = _discover_event_source(
        scrape_request.url,
        soup,
        scrape_request,
    )
    source = strategy.name if strategy else "other"
    failed_events = []

    if strategy:
        if event_links:
            _save_discovered_event_urls(event_links, source=source, city=city)
        else:
            event_links = _load_saved_event_urls(
                source=source,
                city=city,
                max_events=scrape_request.max_events,
            )

        if not event_links:
            raise NoEventLinksError(
                f"No event links found for source '{source}' and no saved links are available."
            )

        parsed_events, failed_events = _scrape_source_events(
            strategy,
            event_links,
            city,
            scrape_request.model_name,
            ollama,
        )
    else:
        parsed = _scrape_generic_events(
            scrape_request.url,
            scrape_request.model_name,
            ollama,
        )

        if not isinstance(parsed, dict) or not isinstance(parsed.get("events"), list):
            raise GenericEventModelError(
                "Could not parse events JSON from model output."
            )
        parsed_events = parsed["events"]

    results = _save_scraped_events(
        parsed_events,
        city,
        failed_events,
        strategy,
    )
    json_output_file = _write_scraped_events_json(
        output_dir,
        scrape_request.url,
        source,
        city,
        results,
    )

    return ScrapeEventsResult(
        json_output_file=json_output_file,
        created_count=results.created_count,
        updated_count=results.updated_count,
        events=results.events,
        failed=results.failed,
    )
