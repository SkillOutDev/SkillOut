import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Mapping

from hello.models import Category, Event


class EventPayloadError(ValueError):
    """Raised when an event request contains invalid values."""


class DuplicateEventError(Exception):
    """Raised when an event with the same name, date, and time already exists."""


@dataclass(frozen=True)
class EventCreationData:
    name: str
    date: date
    time: time
    place: str
    price: Decimal
    short_description: str
    category_names: tuple[str, ...]
    source_url: str | None


def _parse_event_date(value: object) -> date | None:
    if not value:
        return None
    value = str(value).strip()
    normalized = value.replace("–", "-").replace(",", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized_ascii = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")

    month_map = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "sausio": 1,
        "sausis": 1,
        "vasario": 2,
        "vasaris": 2,
        "kovo": 3,
        "kovas": 3,
        "balandzio": 4,
        "balandis": 4,
        "geguzes": 5,
        "geguze": 5,
        "birzelio": 6,
        "birzelis": 6,
        "liepos": 7,
        "liepa": 7,
        "rugpjucio": 8,
        "rugpjutis": 8,
        "rugsejo": 9,
        "rugsejis": 9,
        "spalio": 10,
        "spalis": 10,
        "lapkricio": 11,
        "lapkritis": 11,
        "gruodzio": 12,
        "gruodis": 12,
    }

    lower = normalized_ascii.lower()

    match = re.match(r"^([a-z]+)\s+(\d{1,2})\s*-\s*\d{1,2}\s+(\d{4})$", lower)
    if match and match.group(1) in month_map:
        return datetime(int(match.group(3)), month_map[match.group(1)], int(match.group(2))).date()

    match = re.match(r"^(\d{4})\s+([a-z]+)\s+(\d{1,2})\s*-\s*\d{1,2}$", lower)
    if match and match.group(2) in month_map:
        return datetime(int(match.group(1)), month_map[match.group(2)], int(match.group(3))).date()

    match = re.match(r"^(\d{1,2})\s*-\s*\d{1,2}\s+([a-z]+)\s+(\d{4})$", lower)
    if match and match.group(2) in month_map:
        return datetime(int(match.group(3)), month_map[match.group(2)], int(match.group(1))).date()

    match = re.match(r"^(\d{1,2})\s+([a-z]+)\s+(\d{4})$", lower)
    if match and match.group(2) in month_map:
        return datetime(int(match.group(3)), month_map[match.group(2)], int(match.group(1))).date()

    match = re.match(r"^([a-z]+)\s+(\d{1,2})$", lower)
    if match and match.group(1) in month_map:
        return datetime(datetime.now().year, month_map[match.group(1)], int(match.group(2))).date()

    match = re.match(r"^(\d{1,2})\s+([a-z]+)\s+(\d{4})$", lower)
    if match and match.group(2) in month_map:
        return datetime(int(match.group(3)), month_map[match.group(2)], int(match.group(1))).date()

    formats = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y.%m.%d"]
    for date_format in formats:
        try:
            return datetime.strptime(normalized, date_format).date()
        except ValueError:
            continue

    return None


def _parse_event_time(value: object) -> time | None:
    if not value:
        return None
    value = str(value).strip()
    for time_format in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, time_format).time()
        except ValueError:
            continue
    return None


def _parse_event_price(value: object) -> Decimal | None:
    if value is None:
        return Decimal("0.00")
    raw = str(value).strip().replace("EUR", "").replace("€", "").replace(" ", "")
    raw = raw.replace(",", ".")
    if raw == "" or raw.lower() == "free":
        return Decimal("0.00")
    try:
        return Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def prepare_event_data(data: Mapping[str, object]) -> EventCreationData:
    name = str(data.get("name") or "").strip()
    date_raw = data.get("date")
    time_raw = data.get("time")
    place = str(data.get("place") or "").strip()
    price_raw = data.get("price", 0)
    short_description = str(data.get("short_description") or "").strip()
    category_names = data.get("categories") or []
    source_url = str(data.get("source_url") or "").strip() or None

    if not name:
        raise EventPayloadError("Event title must not be empty")
    if not date_raw:
        raise EventPayloadError("'date' is required (YYYY-MM-DD).")
    if not place:
        raise EventPayloadError("'place' is required.")

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date_raw).strip()):
        raise EventPayloadError("Event date must be in YYYY-MM-DD format")

    date_value = _parse_event_date(date_raw)
    if date_value is None:
        raise EventPayloadError("Event date must be in YYYY-MM-DD format")

    time_value = _parse_event_time(time_raw) if time_raw else None
    if time_raw and time_value is None:
        raise EventPayloadError("Event time must be in HH:mm format")
    if time_value is None:
        time_value = datetime.strptime("00:00", "%H:%M").time()

    price_text = str(price_raw).strip().replace("EUR", "").replace("€", "").replace(" ", "")
    price_text = price_text.replace(",", ".")
    if price_text and price_text.lower() != "free":
        try:
            parsed_price = Decimal(price_text)
        except InvalidOperation:
            parsed_price = None
        if (
            parsed_price is None
            or not parsed_price.is_finite()
            or parsed_price.as_tuple().exponent < -2
            or len(parsed_price.as_tuple().digits)
            + max(parsed_price.as_tuple().exponent, 0)
            > 10
        ):
            raise EventPayloadError(
                "Event price must be a decimal number with up to 2 decimal places"
            )

    price_value = _parse_event_price(price_raw)
    if price_value is None:
        raise EventPayloadError(
            "Event price must be a decimal number with up to 2 decimal places"
        )

    if not isinstance(category_names, list):
        raise EventPayloadError("'categories' must be a list of strings.")

    normalized_category_names = []
    for category_name in category_names:
        if not isinstance(category_name, str):
            raise EventPayloadError("'categories' must be a list of strings.")
        category_name = category_name.strip()
        if category_name:
            normalized_category_names.append(category_name)

    return EventCreationData(
        name=name,
        date=date_value,
        time=time_value,
        place=place,
        price=price_value,
        short_description=short_description,
        category_names=tuple(normalized_category_names),
        source_url=source_url,
    )


def create_event(event_data: EventCreationData) -> Event:
    if Event.objects.filter(
        name=event_data.name,
        date=event_data.date,
        time=event_data.time,
    ).exists():
        raise DuplicateEventError

    event_categories = [
        Category.objects.get_or_create(name=name)[0]
        for name in event_data.category_names
    ]
    event = Event.objects.create(
        name=event_data.name,
        date=event_data.date,
        time=event_data.time,
        place=event_data.place,
        price=event_data.price,
        short_description=event_data.short_description,
        source_url=event_data.source_url,
    )
    event.categories.set(event_categories)
    return event
