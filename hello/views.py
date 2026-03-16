import json
import time
from datetime import datetime
from pathlib import Path
import time
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema

from .models import Category, Student, StudentSubject, Subject


class AddStudentRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class AddCategoryRequestSerializer(serializers.Serializer):
    name = serializers.CharField()


class AddEventRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    date = serializers.DateField()
    time = serializers.TimeField(required=False, allow_null=True)
    place = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    short_description = serializers.CharField(required=False, allow_blank=True, default="")
    categories = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    source_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)


class AddSubjectRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    category_id = serializers.IntegerField(required=False, allow_null=True)


class AddSubjectInterestRequestSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    interest = serializers.IntegerField(min_value=1, max_value=5)


class SubjectInterestUpdateItemSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    interest = serializers.IntegerField(min_value=1, max_value=5)


class BulkUpdateSubjectInterestRequestSerializer(serializers.Serializer):
    subjects = SubjectInterestUpdateItemSerializer(many=True)


class GetStudentSubjectsPathSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()


class ScrapeTextRequestSerializer(serializers.Serializer):
    url = serializers.CharField()
    fromSemester = serializers.IntegerField(required=False)
    toSemester = serializers.IntegerField(required=False)


class ImportSubjectsRequestSerializer(serializers.Serializer):
    study_subjects = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    model = serializers.CharField(required=False)


class ScrapeImportAssignRequestSerializer(serializers.Serializer):
    url = serializers.CharField()
    fromSemester = serializers.IntegerField(required=False)
    toSemester = serializers.IntegerField(required=False)
    model = serializers.CharField(required=False)


class ScrapeEventsRequestSerializer(serializers.Serializer):
    url = serializers.CharField()
    model = serializers.CharField(required=False)
    max_events = serializers.IntegerField(required=False)
    city = serializers.CharField(required=False, allow_blank=True)


class FilterEventsQuerySerializer(serializers.Serializer):
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    city = serializers.CharField(required=False, allow_blank=True)
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)


class SubjectItemSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    name = serializers.CharField()
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)
    interest = serializers.IntegerField()
    interest_description = serializers.CharField(allow_null=True)


class StudentSubjectsResponseSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_username = serializers.CharField()
    subjects = SubjectItemSerializer(many=True)
    total_subjects = serializers.IntegerField()


def _normalize_subject_names(raw_subjects):
    """Convert noisy AI output into a clean, deduplicated list of subject names."""
    if not isinstance(raw_subjects, list):
        return []

    cleaned = []
    seen = set()
    skip_tokens = {
        "{",
        "}",
        "[",
        "]",
        '"study_subjects": [',
        'study_subjects": [',
        'study_subjects\\": [',
            subjects_data = get_student_subjects_with_interest_levels(student)
            continue
        if compact.startswith("study_subjects\":[") or compact.startswith("study_subjects:["):
            continue

        key = value.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

        @extend_schema(
            request=GetStudentSubjectsPathSerializer,
            responses={200: StudentSubjectsResponseSerializer, 404: serializers.DictField()},
        )
        @api_view(["GET"])
        def get_student_subjects_with_interest_levels(student):
            """Return all subjects with the given student's optional interest level."""
            student_subjects = StudentSubject.objects.filter(student=student).select_related("subject__category")
            interest_by_subject_id = {ss.subject_id: ss.interest for ss in student_subjects}
            interest_map = dict(StudentSubject.INTEREST_CHOICES)

            subjects_data = []
            for subject in Subject.objects.select_related("category").order_by("name"):
                interest = interest_by_subject_id.get(subject.id)
                subjects_data.append(
                    {
                        "subject_id": subject.id,
                        "name": subject.name,
                        "category_id": subject.category.id if subject.category else None,
                        "category_name": subject.category.name if subject.category else None,
                        "interest": interest,
                        "interest_description": interest_map.get(interest),
                    }
                )

            return subjects_data
    return cleaned


def _extract_subject_names_from_ollama_output(raw_content):
    parsed = None
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(raw_content[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if isinstance(parsed, dict) and isinstance(parsed.get("study_subjects"), list):
        return _normalize_subject_names(parsed["study_subjects"])

    fallback = [
        line.strip("-• \t")
        for line in raw_content.splitlines()
        if line.strip("-• \t")
    ]
    return _normalize_subject_names(fallback)


def _classify_subject_category(subject_name, model):
    import ollama

    prompt = (
        "You are classifying a university study subject into a broad category. "
        "Return strict JSON only in this format: {\"category\": \"Category Name\"}. "
        "Examples of categories: IT, Mathematics, Business, Architecture, Engineering, Law. "
        "Do not add explanation.\n\n"
        f"Subject: {subject_name}"
    )

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.get("message", {}).get("content", "").strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    parsed = json.loads(raw)
    category_name = str(parsed.get("category", "")).strip()
    if not category_name:
        raise ValueError("Model returned an empty category")
    return category_name


# Temporary auth substitute: until authentication is implemented,
# treat student with ID=1 as the current logged-in student.
DEFAULT_STUDENT_ID = 1
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from .models import Student, Category, Subject, StudentSubject, Event, EventPageUrl
import json

import os


def _parse_event_date(value):
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
        # Lithuanian month forms (genitive and nominative)
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

    # Patterns like: "May 2-3 2026" or "October 23-25 2026"
    m = re.match(r"^([a-z]+)\s+(\d{1,2})\s*-\s*\d{1,2}\s+(\d{4})$", lower)
    if m and m.group(1) in month_map:
        return datetime(int(m.group(3)), month_map[m.group(1)], int(m.group(2))).date()

    # Patterns like: "2026 May 22-24"
    m = re.match(r"^(\d{4})\s+([a-z]+)\s+(\d{1,2})\s*-\s*\d{1,2}$", lower)
    if m and m.group(2) in month_map:
        return datetime(int(m.group(1)), month_map[m.group(2)], int(m.group(3))).date()

    # Patterns like: "15-17 May 2026"
    m = re.match(r"^(\d{1,2})\s*-\s*\d{1,2}\s+([a-z]+)\s+(\d{4})$", lower)
    if m and m.group(2) in month_map:
        return datetime(int(m.group(3)), month_map[m.group(2)], int(m.group(1))).date()

    # Patterns like: "20 March 2026"
    m = re.match(r"^(\d{1,2})\s+([a-z]+)\s+(\d{4})$", lower)
    if m and m.group(2) in month_map:
        return datetime(int(m.group(3)), month_map[m.group(2)], int(m.group(1))).date()

    # Patterns like: "kovo 21" (year missing -> current year)
    m = re.match(r"^([a-z]+)\s+(\d{1,2})$", lower)
    if m and m.group(1) in month_map:
        return datetime(datetime.now().year, month_map[m.group(1)], int(m.group(2))).date()

    # Patterns like: "21 kovo 2026"
    m = re.match(r"^(\d{1,2})\s+([a-z]+)\s+(\d{4})$", lower)
    if m and m.group(2) in month_map:
        return datetime(int(m.group(3)), month_map[m.group(2)], int(m.group(1))).date()

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y.%m.%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue

    return None


def _parse_event_time(value):
    if not value:
        return None
    value = str(value).strip()
    formats = ["%H:%M", "%H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def _parse_event_price(value):
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
        if "/find/" in parsed.path:
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


def _build_event_prompt(source, detail_url, detail_text, city=""):
    if source == "litexpo":
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

    if source == "meetup":
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

    if source == "kaveikti":
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

    return (
        "Extract ONE event from this detail page text and return strict JSON only. "
        "Output format: "
        '{"name": "", "date": "YYYY-MM-DD", "time": "HH:MM", "place": "", "price": "", '
        '"categories": [""], "short_description": ""}. '
        "If price is not provided, use 0. If time is missing, use 00:00. "
        "Do not include markdown or explanation.\n\n"
        f"Source URL: {detail_url}\n"
        f"Detail page text:\n{detail_text}"
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

# Create your views here.

def home(request):
    return HttpResponse("Hello, world!")

def hello_there(request, name):
    print(request.build_absolute_uri()) #optional
    return render(
        request,
        'hello/hello_there.html',
        {
            'name': name,
            'date': datetime.now()
        }
    )

@extend_schema(
    request=AddStudentRequestSerializer,
    responses={201: serializers.DictField(), 400: serializers.DictField()},
)
@api_view(["POST"])
def add_student(request):
    data = request.data
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")

    if not username or not password:
        return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    student = Student.objects.create(user=user)

    return Response(
        {
            "message": "Student created successfully",
            "student_id": student.id,
            "user_id": user.id,
        },
        status=status.HTTP_201_CREATED,
    )

@extend_schema(
    request=AddCategoryRequestSerializer,
    responses={201: serializers.DictField(), 400: serializers.DictField()},
)
@api_view(["POST"])
def add_category(request):
    data = request.data
    name = data.get("name")

    if not name:
        return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)

    if Category.objects.filter(name=name).exists():
        return Response({"error": "Category already exists"}, status=status.HTTP_400_BAD_REQUEST)

    category = Category.objects.create(name=name)
    return Response(
        {
            "message": "Category created successfully",
            "category_id": category.id,
            "name": category.name,
        },
        status=status.HTTP_201_CREATED,
    )

@extend_schema(
    request=AddSubjectRequestSerializer,
    responses={201: serializers.DictField(), 400: serializers.DictField()},
)
@api_view(["POST"])
def add_subject(request):
    data = request.data
    name = data.get("name")
    category_id = data.get("category_id")

    if not name:
        return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)

    if Subject.objects.filter(name=name).exists():
        return Response({"error": "Subject already exists"}, status=status.HTTP_400_BAD_REQUEST)

    category = None
    if category_id:
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"error": "Category not found"}, status=status.HTTP_400_BAD_REQUEST)

    subject = Subject.objects.create(name=name, category=category)
    return Response(
        {
            "message": "Subject created successfully",
            "subject_id": subject.id,
            "name": subject.name,
            "category_id": category.id if category else None,
            "category_name": category.name if category else None,
        },
        status=status.HTTP_201_CREATED,
    )

@extend_schema(
    request=AddSubjectInterestRequestSerializer,
    responses={201: serializers.DictField(), 400: serializers.DictField(), 404: serializers.DictField()},
)
@api_view(["POST"])
def add_subject_interest(request):
    data = request.data
    # Hardcoded current student for now (no auth yet).
    student_id = DEFAULT_STUDENT_ID
    subject_id = data.get("subject_id")
    interest = data.get("interest")

    if not all([subject_id, interest]):
        return Response(
            {"error": "subject_id and interest are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        interest = int(interest)
    except (TypeError, ValueError):
        return Response({"error": "Interest must be a number"}, status=status.HTTP_400_BAD_REQUEST)

    if interest not in [1, 2, 3, 4, 5]:
        return Response({"error": "Interest must be between 1 and 5"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response(
            {"error": f"Hardcoded student id {DEFAULT_STUDENT_ID} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        return Response({"error": "Subject not found"}, status=status.HTTP_404_NOT_FOUND)

    student_subject, created = StudentSubject.objects.update_or_create(
        student=student,
        subject=subject,
        defaults={"interest": interest},
    )

    return Response(
        {
            "message": "Interest level updated successfully" if not created else "Interest level set successfully",
            "student_id": student_id,
            "subject_id": subject_id,
            "interest": interest,
            "created": created,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    request=BulkUpdateSubjectInterestRequestSerializer,
    responses={200: serializers.DictField(), 400: serializers.DictField(), 404: serializers.DictField()},
)
@api_view(["PUT"])
def update_student_subject_interests(request):
    data = request.data if isinstance(request.data, dict) else {}
    items = data.get("subjects")

    if not isinstance(items, list) or not items:
        return Response(
            {"error": "Field 'subjects' is required and must be a non-empty list."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        student = Student.objects.get(id=DEFAULT_STUDENT_ID)
    except Student.DoesNotExist:
        return Response(
            {"error": f"Hardcoded student id {DEFAULT_STUDENT_ID} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    updated = []
    failed = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            failed.append({"index": idx, "error": "Each subjects item must be an object."})
            continue

        subject_id = item.get("subject_id")
        interest = item.get("interest")

        if subject_id is None or interest is None:
            failed.append(
                {
                    "index": idx,
                    "subject_id": subject_id,
                    "error": "subject_id and interest are required",
                }
            )
            continue

        try:
            interest = int(interest)
        except (TypeError, ValueError):
            failed.append(
                {
                    "index": idx,
                    "subject_id": subject_id,
                    "error": "Interest must be a number",
                }
            )
            continue

        if interest not in [1, 2, 3, 4, 5]:
            failed.append(
                {
                    "index": idx,
                    "subject_id": subject_id,
                    "error": "Interest must be between 1 and 5",
                }
            )
            continue

        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            failed.append(
                {
                    "index": idx,
                    "subject_id": subject_id,
                    "error": "Subject not found",
                }
            )
            continue

        try:
            student_subject = StudentSubject.objects.get(student=student, subject=subject)
        except StudentSubject.DoesNotExist:
            failed.append(
                {
                    "index": idx,
                    "subject_id": subject_id,
                    "error": "Student-subject relation not found",
                }
            )
            continue

        student_subject.interest = interest
        student_subject.save(update_fields=["interest"])
        updated.append(
            {
                "subject_id": subject.id,
                "subject_name": subject.name,
                "interest": interest,
            }
        )

    return Response(
        {
            "message": "Bulk update completed.",
            "student_id": student.id,
            "updated_count": len(updated),
            "failed_count": len(failed),
            "updated": updated,
            "failed": failed,
        },
        status=status.HTTP_200_OK,
    )


def build_student_subjects_with_interest(student):
    """Return student's linked subjects with interest levels and category metadata."""
    student_subjects = StudentSubject.objects.filter(student=student).select_related("subject__category")
    interest_map = dict(StudentSubject.INTEREST_CHOICES)

    subjects_data = []
    for ss in student_subjects:
        subject = ss.subject
        subjects_data.append(
            {
                "subject_id": subject.id,
                "name": subject.name,
                "category_id": subject.category.id if subject.category else None,
                "category_name": subject.category.name if subject.category else None,
                "interest": ss.interest,
                "interest_description": interest_map.get(ss.interest),
            }
        )

    return subjects_data

@extend_schema(
    request=GetStudentSubjectsPathSerializer,
    responses={200: StudentSubjectsResponseSerializer, 404: serializers.DictField()},
)
@api_view(["GET"])
def get_student_subjects(request, student_id):
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    subjects_data = build_student_subjects_with_interest(student)

    return Response(
        {
            "student_id": student_id,
            "student_username": student.user.username,
            "subjects": subjects_data,
            "total_subjects": len(subjects_data),
        },
        status=status.HTTP_200_OK,
    )

@extend_schema(
    request=ScrapeTextRequestSerializer,
    responses={200: serializers.DictField(), 400: serializers.DictField(), 500: serializers.DictField()},
)
@api_view(["POST"])
def scrape_text(request):
    payload = request.data if isinstance(request.data, dict) else {}

    url = (payload.get("url") or "").strip()
    if "fromSemester" not in payload or "toSemester" not in payload:
        return JsonResponse(
            {"error": "Fields 'fromSemester' and 'toSemester' are required."},
            status=400,
        )

    from_semester = payload.get("fromSemester")
    to_semester = payload.get("toSemester")

    try:
        from_semester = int(from_semester)
        to_semester = int(to_semester)
    except (TypeError, ValueError):
        return Response({"error": "fromSemester and toSemester must be numbers."}, status=status.HTTP_400_BAD_REQUEST)

    if from_semester < 1 or to_semester < 1:
        return JsonResponse({"error": "fromSemester and toSemester must be at least 1."}, status=400)

    if from_semester > 8 or to_semester > 8:
        return JsonResponse({"error": "fromSemester and toSemester must be at most 8."}, status=400)

    if from_semester > to_semester:
        return Response({"error": "fromSemester cannot be greater than toSemester."}, status=status.HTTP_400_BAD_REQUEST)
    if not url:
        return Response({"error": "Field 'url' is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not (url.startswith("http://") or url.startswith("https://")):
        return Response({"error": "URL must start with http:// or https://."}, status=status.HTTP_400_BAD_REQUEST)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.HTTPError as e:
            return Response({"error": f"HTTP error: {e.response.status_code}"}, status=status.HTTP_400_BAD_REQUEST)
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == max_retries - 1:
                return Response({"error": f"Failed after {max_retries} attempts: {e}"}, status=status.HTTP_400_BAD_REQUEST)
            time.sleep(1)
        except requests.RequestException as e:
            return Response({"error": f"Request failed: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(["script", "style", "noscript"]):
        element.extract()

    text = soup.get_text(separator=" ", strip=True)[:60000]

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_output_file = output_dir / "latest_scrape.txt"
    txt_output_file.write_text(text, encoding="utf-8")

    try:
        import ollama
    except ImportError:
        return Response(
            {"error": "Ollama Python package is not installed. Install it with: pip install ollama"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # prompt = (
    #     "Extract only study subject names from semesters "
    #     f"{from_semester} to {to_semester} from the provided webpage text. "
    #     f"That means study subjects are between text for {from_semester} semester to {to_semester + 1} semester. "
    #     "Do not translate or modify original subject text. "
    #     "Return strict JSON only in this format: "
    #     '{"study_subjects": ["subject 1", "subject 2"]}. '
    #     "No markdown, no explanation.\n\n"
    #     f"Webpage text:\n{text}"
    # )

    prompt = (
    "Task: Extract study subjects only from selected semesters.\n"
    f"Selected semesters: {from_semester} to {to_semester} (inclusive).\n\n"
    "Strict rules:\n"
    "1) Include subject only if it is clearly listed under semester number "
    f"{from_semester}..{to_semester}.\n"
    "2) Exclude all subjects from any semester outside that range.\n"
    "3) If semester is unclear, exclude it.\n"
    "4) Keep original subject text exactly (no translation, no rewriting).\n"
    "5) Remove duplicates.\n"
    "6) Output ONLY valid JSON with one key exactly:\n"
    '{"study_subjects":["...","..."]}\n'
    "7) Do not output markdown, comments, explanations, or extra keys.\n\n"
    "Webpage text:\n"
    f"{text}"
)

    try:
        ollama_response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "top_p": 0.1}
        )
    except Exception as exc:
        return Response({"error": f"Ollama request failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    raw_content = ollama_response.get("message", {}).get("content", "").strip()

    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

    subjects = _extract_subject_names_from_ollama_output(raw_content)

    json_output = {
        "url": url,
        "from_semester": from_semester,
        "to_semester": to_semester,
        "study_subjects": subjects,
    }

    json_output_file = output_dir / "latest_subjects.json"
    json_output_file.write_text(
        json.dumps(json_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result_message = "Scrape and AI extraction completed successfully."
    if not subjects:
        result_message = "No results found for the selected semester range."

    return Response(
        {
            "message": result_message,
            "file": str(txt_output_file.relative_to(settings.BASE_DIR)),
            "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
            "characters": len(text),
            "subjects_count": len(subjects),
            "study_subjects": subjects,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=ImportSubjectsRequestSerializer,
    responses={200: serializers.DictField(), 400: serializers.DictField(), 500: serializers.DictField()},
)
@api_view(["POST"])
def import_subjects_with_categories(request):
    payload = request.data if isinstance(request.data, dict) else {}
    model = (payload.get("model") or "llama3").strip()
    incoming_subjects = payload.get("study_subjects")

    if incoming_subjects is None:
        latest_file = Path(settings.BASE_DIR) / "scraped_text" / "latest_subjects.json"
        if not latest_file.exists():
            return Response(
                {
                    "error": "No study_subjects provided and scraped_text/latest_subjects.json was not found."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            file_payload = json.loads(latest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return Response(
                {"error": "latest_subjects.json is not valid JSON."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        incoming_subjects = file_payload.get("study_subjects", [])

    subjects = _normalize_subject_names(incoming_subjects)
    if not subjects:
        return Response(
            {"error": "No valid subjects found after normalization."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        import ollama
        ollama.list()
    except ImportError:
        return Response(
            {"error": "Ollama Python package is not installed. Install it with: pip install ollama"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:
        return Response(
            {"error": f"Ollama is not available: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    created_categories = 0
    created_subjects = 0
    updated_subjects = 0
    failed = []
    processed = []

    for subject_name in subjects:
        try:
            category_name = _classify_subject_category(subject_name, model)

            category = Category.objects.filter(name__iexact=category_name).first()
            if category is None:
                category = Category.objects.create(name=category_name)
                created_categories += 1

            subject = Subject.objects.filter(name__iexact=subject_name).first()
            if subject is None:
                Subject.objects.create(name=subject_name, category=category)
                created_subjects += 1
                action = "created"
            else:
                action = "unchanged"
                if subject.category_id != category.id:
                    subject.category = category
                    subject.save(update_fields=["category"])
                    updated_subjects += 1
                    action = "updated"

            processed.append(
                {
                    "subject": subject_name,
                    "category": category.name,
                    "action": action,
                }
            )
        except Exception as exc:
            failed.append({"subject": subject_name, "error": str(exc)})

    return Response(
        {
            "message": "Subject import completed.",
            "model": model,
            "input_count": len(subjects),
            "created_categories": created_categories,
            "created_subjects": created_subjects,
            "updated_subjects": updated_subjects,
            "failed_count": len(failed),
            "processed": processed,
            "failed": failed,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=ScrapeImportAssignRequestSerializer,
    responses={200: serializers.DictField(), 400: serializers.DictField(), 404: serializers.DictField(), 500: serializers.DictField()},
)
@api_view(["POST"])
def scrape_import_and_assign_subjects(request):
    payload = request.data if isinstance(request.data, dict) else {}
    url = (payload.get("url") or "").strip()
    from_semester = payload.get("fromSemester", 1)
    to_semester = payload.get("toSemester", 4)
    model = (payload.get("model") or "llama3").strip()

    if not url:
        return Response({"error": "Field 'url' is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not (url.startswith("http://") or url.startswith("https://")):
        return Response({"error": "URL must start with http:// or https://."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from_semester = int(from_semester)
        to_semester = int(to_semester)
    except (TypeError, ValueError):
        return Response({"error": "fromSemester and toSemester must be numbers."}, status=status.HTTP_400_BAD_REQUEST)

    if from_semester > to_semester:
        return Response({"error": "fromSemester cannot be greater than toSemester."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = Student.objects.get(id=DEFAULT_STUDENT_ID)
    except Student.DoesNotExist:
        return Response(
            {
                "error": f"Hardcoded student id {DEFAULT_STUDENT_ID} does not exist.",
                "hint": "Create a student first using /add-student/.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.HTTPError as e:
            return Response({"error": f"HTTP error: {e.response.status_code}"}, status=status.HTTP_400_BAD_REQUEST)
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == max_retries - 1:
                return Response(
                    {"error": f"Failed after {max_retries} attempts: {e}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            time.sleep(1)
        except requests.RequestException as e:
            return Response({"error": f"Request failed: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.extract()
    text = soup.get_text(separator=" ", strip=True)[:60000]

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_output_file = output_dir / "latest_scrape.txt"
    txt_output_file.write_text(text, encoding="utf-8")

    try:
        import ollama
        ollama.list()
    except ImportError:
        return Response(
            {"error": "Ollama Python package is not installed. Install it with: pip install ollama"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:
        return Response(
            {"error": f"Ollama is not available: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    prompt = (
        "Task: Extract study subjects only from selected semesters.\n"
        f"Selected semesters: {from_semester} to {to_semester} (inclusive).\n\n"
        "Strict rules:\n"
        "1) Include subject only if it is clearly listed under semester number "
        f"{from_semester}..{to_semester}.\n"
        "2) Exclude all subjects from any semester outside that range.\n"
        "3) If semester is unclear, exclude it.\n"
        "4) Keep original subject text exactly (no translation, no rewriting).\n"
        "5) Remove duplicates.\n"
        "6) Output ONLY valid JSON with one key exactly:\n"
        '{"study_subjects":["...","..."]}\n'
        "7) Do not output markdown, comments, explanations, or extra keys.\n\n"
        "Webpage text:\n"
        f"{text}"
    )

    try:
        ollama_response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "top_p": 0.1},
        )
    except Exception as exc:
        return Response(
            {"error": f"Ollama request failed: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    raw_content = ollama_response.get("message", {}).get("content", "").strip()
    subjects = _extract_subject_names_from_ollama_output(raw_content)

    json_output = {
        "url": url,
        "from_semester": from_semester,
        "to_semester": to_semester,
        "study_subjects": subjects,
    }
    json_output_file = output_dir / "latest_subjects.json"
    json_output_file.write_text(
        json.dumps(json_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not subjects:
        return Response(
            {
                "message": "No results found for the selected semester range.",
                "file": str(txt_output_file.relative_to(settings.BASE_DIR)),
                "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
                "student_id": student.id,
                "subjects_count": 0,
                "assigned_count": 0,
            },
            status=status.HTTP_200_OK,
        )

    created_categories = 0
    created_subjects = 0
    updated_subjects = 0
    assigned_count = 0
    failed = []
    processed = []

    for subject_name in subjects:
        try:
            category_name = _classify_subject_category(subject_name, model)

            category = Category.objects.filter(name__iexact=category_name).first()
            if category is None:
                category = Category.objects.create(name=category_name)
                created_categories += 1

            subject = Subject.objects.filter(name__iexact=subject_name).first()
            if subject is None:
                subject = Subject.objects.create(name=subject_name, category=category)
                created_subjects += 1
                subject_action = "created"
            else:
                subject_action = "unchanged"
                if subject.category_id != category.id:
                    subject.category = category
                    subject.save(update_fields=["category"])
                    updated_subjects += 1
                    subject_action = "updated"

            _, assigned_created = StudentSubject.objects.get_or_create(
                student=student,
                subject=subject,
                defaults={"interest": None},
            )

            if assigned_created:
                assigned_count += 1

            processed.append(
                {
                    "subject": subject_name,
                    "category": category.name,
                    "subject_action": subject_action,
                    "assigned": True,
                    "assignment_action": "created" if assigned_created else "existing",
                }
            )
        except Exception as exc:
            failed.append({"subject": subject_name, "error": str(exc)})

    return Response(
        {
            "message": "Scrape, import, and assignment completed.",
            "model": model,
            "student_id": student.id,
            "input_count": len(subjects),
            "created_categories": created_categories,
            "created_subjects": created_subjects,
            "updated_subjects": updated_subjects,
            "assigned_count": assigned_count,
            "failed_count": len(failed),
            "file": str(txt_output_file.relative_to(settings.BASE_DIR)),
            "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
            "processed": processed,
            "failed": failed,
        },
        status=status.HTTP_200_OK,
    )

@extend_schema(
    request=ScrapeEventsRequestSerializer,
    responses={200: serializers.DictField(), 400: serializers.DictField(), 500: serializers.DictField()},
)
@api_view(["POST"])
def scrape_events(request):
    payload = request.data if isinstance(request.data, dict) else {}

    url = (payload.get("url") or "").strip()
    model_name = (payload.get("model") or "llama3").strip()
    max_events = payload.get("max_events", 20)
    city = (payload.get("city") or "").strip()

    try:
        max_events = int(max_events)
    except (TypeError, ValueError):
        return Response({"error": "max_events must be a number."}, status=status.HTTP_400_BAD_REQUEST)
    if max_events < 1:
        return Response({"error": "max_events must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
    if not url:
        return Response({"error": "Field 'url' is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not (url.startswith("http://") or url.startswith("https://")):
        return Response({"error": "URL must start with http:// or https://."}, status=status.HTTP_400_BAD_REQUEST)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.HTTPError as e:
            return Response({"error": f"HTTP error: {e.response.status_code}"}, status=status.HTTP_400_BAD_REQUEST)
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == max_retries - 1:
                return Response({"error": f"Failed after {max_retries} attempts: {e}"}, status=status.HTTP_400_BAD_REQUEST)
            time.sleep(1)
        except requests.RequestException as e:
            return Response({"error": f"Request failed: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    soup = BeautifulSoup(response.text, "html.parser")

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import ollama
    except ImportError:
        return Response(
            {"error": "Ollama Python package is not installed. Install it with: pip install ollama"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    parsed = {"events": []}
    failed_events = []

    source = "other"
    parsed_url = urlparse(url)
    host = parsed_url.netloc.lower()
    path = parsed_url.path.lower()

    if "litexpo.lt" in host and "/en/events" in path:
        source = "litexpo"
        event_links = _extract_litexpo_event_links(soup, url, max_events=max_events)
    elif "meetup.com" in host and "/find/" in path:
        source = "meetup"
        event_links = _extract_meetup_event_links(soup, url, max_events=max_events)
        if not city:
            location_param = payload.get("location") or ""
            if location_param:
                city = str(location_param).split("--")[-1]
            elif "location=" in parsed_url.query:
                for part in parsed_url.query.split("&"):
                    if part.startswith("location="):
                        city = part.split("=", 1)[-1].split("--")[-1]
                        break
    elif "kaveikti.lt" in host and "/renginiai" in path:
        source = "kaveikti"
        event_links = _extract_kaveikti_event_links(soup, url, max_events=max_events)
    else:
        event_links = []

    if source in {"litexpo", "meetup", "kaveikti"}:
        if event_links:
            _save_discovered_event_urls(event_links, source=source, city=city)
        else:
            event_links = _load_saved_event_urls(source=source, city=city, max_events=max_events)

        if not event_links:
            return Response(
                {"error": f"No event links found for source '{source}' and no saved links are available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for detail_url in event_links:
            try:
                detail_text = _get_clean_page_text(detail_url)
            except Exception as exc:
                failed_events.append({"source_url": detail_url, "error": f"Failed to open detail page: {exc}"})
                continue

            prompt = _build_event_prompt(source=source, detail_url=detail_url, detail_text=detail_text, city=city)

            try:
                ollama_response = ollama.chat(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as exc:
                failed_events.append({"source_url": detail_url, "error": f"Ollama request failed: {exc}"})
                continue

            model_payload = _parse_json_from_model_output(
                ollama_response.get("message", {}).get("content", "")
            )
            if not isinstance(model_payload, dict):
                failed_events.append({"source_url": detail_url, "error": "Could not parse model JSON output."})
                continue

            model_payload["source_url"] = detail_url
            parsed["events"].append(model_payload)

            EventPageUrl.objects.filter(url=detail_url).update(last_scraped=timezone.now())
    else:
        text = _get_clean_page_text(url)
        prompt = (
            "Extract events from the webpage text and return strict JSON only. "
            "Output format: "
            '{"events": [{"name": "", "date": "YYYY-MM-DD", "time": "HH:MM", "place": "", "price": "", '
            '"categories": [""], "short_description": ""}]}. '
            "If price is not provided, use 0. If time is missing, use 00:00. "
            "Do not include markdown or extra explanation.\n\n"
            f"Webpage text:\n{text}"
        )

        try:
            ollama_response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            return Response({"error": f"Ollama request failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        parsed = _parse_json_from_model_output(ollama_response.get("message", {}).get("content", ""))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("events"), list):
            return Response({"error": "Could not parse events JSON from model output."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    created_events = 0
    updated_events = 0
    saved_events = []

    for item in parsed["events"]:
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
            if source == "litexpo":
                place = "LITEXPO, Vilnius"
            elif source == "meetup" and city:
                place = city
            else:
                place = ""

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
            cat_name = str(category_name).strip()
            if not cat_name:
                continue
            category, _ = Category.objects.get_or_create(name=cat_name)
            event_categories.append(category)

        if event_categories:
            event.categories.set(event_categories)

        if created:
            created_events += 1
        else:
            updated_events += 1

        saved_events.append(
            {
                "event_id": event.id,
                "name": event.name,
                "date": str(event.date),
                "time": event.time.strftime("%H:%M"),
                "place": event.place,
                "price": str(event.price),
                "categories": [c.name for c in event.categories.all()],
                "short_description": event.short_description,
                "source_url": event.source_url,
            }
        )

    events_output = {
        "url": url,
        "source": source,
        "city": city,
        "events": saved_events,
        "failed": failed_events,
    }
    json_output_file = output_dir / "latest_events.json"
    json_output_file.write_text(
        json.dumps(events_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return Response(
        {
            "message": "Event scrape and extraction completed.",
            "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
            "created_events": created_events,
            "updated_events": updated_events,
            "failed_count": len(failed_events),
            "events": saved_events,
            "failed": failed_events,
        },
        status=status.HTTP_200_OK,
    )


# This view is for testing purposes to retrieve the latest scraped subjects from the JSON file.
def get_latest_subjects(request):
    # SVARBU: Failas yra 'scraped_text' aplanke, todėl turime jį įtraukti į kelią
    file_path = os.path.join(settings.BASE_DIR, 'scraped_text', 'latest_subjects.json')
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data)
    
    # Jei failo nėra, grąžiname klaidą su tiksliu keliu (kad žinotume, kur jis ieško)
    return JsonResponse({
        "error": "File not found", 
        "searched_at": str(file_path)
    }, status=404)


def get_latest_events(request):
    file_path = os.path.join(settings.BASE_DIR, 'scraped_text', 'latest_events.json')

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data)

    return JsonResponse(
        {
            "error": "File not found",
            "searched_at": str(file_path),
        },
        status=404,
    )


def _event_to_json(event):
    return {
        "event_id": event.id,
        "name": event.name,
        "date": str(event.date),
        "time": event.time.strftime("%H:%M") if event.time else "",
        "place": event.place,
        "price": str(event.price),
        "categories": [c.name for c in event.categories.all()],
        "short_description": event.short_description,
        "source_url": event.source_url,
    }


def _events_to_json(events):
    return [_event_to_json(e) for e in events]


def search_events_by_subject_category(subject):
    """Find events whose categories match the given subject's category.

    Accepts a Subject instance, subject id, or subject name. Returns a list of Event objects.
    """
    subject_obj = None

    if isinstance(subject, Subject):
        subject_obj = subject
    elif isinstance(subject, int):
        subject_obj = Subject.objects.filter(id=subject).select_related("category").first()
    elif isinstance(subject, str):
        subject_obj = Subject.objects.filter(name__iexact=subject.strip()).select_related("category").first()

    if not subject_obj or not subject_obj.category or not subject_obj.category.name:
        return []

    category_name = subject_obj.category.name.strip().lower()
    events = Event.objects.prefetch_related("categories").order_by("-date", "-time")

    return [
        event
        for event in events
        if any((c.name or "").strip().lower() == category_name for c in event.categories.all())
    ]


def get_events_similar_to_student_subjects(student):
    """Return events that match categories of student's subjects with interest > 0."""
    base_events = Event.objects.prefetch_related("categories").order_by("-date", "-time")

    student_subjects = StudentSubject.objects.filter(
        student=student,
        interest__gt=0,
    ).select_related("subject__category")

    category_names = {
        ss.subject.category.name.strip().lower()
        for ss in student_subjects
        if ss.subject and ss.subject.category and ss.subject.category.name
    }

    similar_events = [
        event
        for event in base_events
        if any((c.name or "").strip().lower() in category_names for c in event.categories.all())
    ]

    return similar_events, sorted(category_names)


@api_view(["GET"])
def get_events(request):
    """Return all events stored in the database, newest first."""
    events = Event.objects.prefetch_related("categories").order_by("-date", "-time")

    data = _events_to_json(events)

    return Response({"total": len(data), "events": data}, status=status.HTTP_200_OK)


@extend_schema(
    request=GetStudentSubjectsPathSerializer,
    responses={200: serializers.DictField(), 404: serializers.DictField()},
)
@api_view(["GET"])
def get_events_for_student_categories(request, student_id):
    """Return only events similar to the student's interested subject categories."""
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    events_queryset, used_categories = get_events_similar_to_student_subjects(student)
    data = _events_to_json(events_queryset)

    return Response(
        {
            "student_id": student_id,
            "mode": "matched-only",
            "categories_used": used_categories,
            "total": len(data),
            "events": data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    parameters=[FilterEventsQuerySerializer],
    responses={200: serializers.DictField(), 400: serializers.DictField()},
)
@api_view(["GET"])
def filter_events(request):
    """Filter events by price range, date range, city, and time range."""
    serializer = FilterEventsQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    filters = serializer.validated_data

    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    city = (filters.get("city") or "").strip()
    start_time = filters.get("start_time")
    end_time = filters.get("end_time")

    if min_price is not None and max_price is not None and min_price > max_price:
        return Response(
            {"error": "min_price cannot be greater than max_price."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if start_date and end_date and start_date > end_date:
        return Response(
            {"error": "start_date cannot be greater than end_date."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if start_time and end_time and start_time > end_time:
        return Response(
            {"error": "start_time cannot be greater than end_time."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    events = Event.objects.prefetch_related("categories").order_by("date", "time")

    if min_price is not None:
        events = events.filter(price__gte=min_price)
    if max_price is not None:
        events = events.filter(price__lte=max_price)
    if start_date is not None:
        events = events.filter(date__gte=start_date)
    if end_date is not None:
        events = events.filter(date__lte=end_date)
    if city:
        events = events.filter(place__icontains=city)
    if start_time is not None:
        events = events.filter(time__gte=start_time)
    if end_time is not None:
        events = events.filter(time__lte=end_time)

    data = _events_to_json(events)

    return Response({"total": len(data), "events": data}, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: serializers.DictField(), 404: serializers.DictField()},
)
@api_view(["GET"])
def get_event_by_id(request, event_id):
    """Return a single event by id with full details."""
    try:
        event = Event.objects.prefetch_related("categories").get(id=event_id)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(_event_to_json(event), status=status.HTTP_200_OK)


@extend_schema(
    responses={200: serializers.DictField()},
)
@api_view(["DELETE"])
def purge_ended_events(request):
    """Delete all events whose date+time is in the past."""
    now = timezone.now()
    today = now.date()
    current_time = now.time()

    # Events on a past date, or today but the time has already passed
    ended = Event.objects.filter(
        date__lt=today
    ) | Event.objects.filter(
        date=today, time__lt=current_time
    )

    deleted_events = [
        {"event_id": e.id, "name": e.name, "date": str(e.date), "time": e.time.strftime("%H:%M")}
        for e in ended
    ]
    count = ended.count()
    ended.delete()

    return Response(
        {
            "message": f"{count} ended event(s) removed.",
            "deleted_count": count,
            "deleted_events": deleted_events,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=AddEventRequestSerializer,
    responses={201: serializers.DictField(), 200: serializers.DictField(), 400: serializers.DictField()},
)
@api_view(["POST"])
def add_event(request):
    data = request.data
    name = str(data.get("name") or "").strip()
    date_raw = data.get("date")
    time_raw = data.get("time")
    place = str(data.get("place") or "").strip()
    price_raw = data.get("price", 0)
    short_description = str(data.get("short_description") or "").strip()
    category_names = data.get("categories") or []
    source_url = str(data.get("source_url") or "").strip() or None

    if not name:
        return Response({"error": "'name' is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not date_raw:
        return Response({"error": "'date' is required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
    if not place:
        return Response({"error": "'place' is required."}, status=status.HTTP_400_BAD_REQUEST)

    date_value = _parse_event_date(date_raw)
    if date_value is None:
        return Response({"error": "Invalid 'date' format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    time_value = _parse_event_time(time_raw) if time_raw else None
    if time_value is None:
        time_value = datetime.strptime("00:00", "%H:%M").time()

    price_value = _parse_event_price(price_raw)
    if price_value is None:
        return Response({"error": "Invalid 'price' value."}, status=status.HTTP_400_BAD_REQUEST)

    if not isinstance(category_names, list):
        return Response({"error": "'categories' must be a list of strings."}, status=status.HTTP_400_BAD_REQUEST)

    event, created = Event.objects.update_or_create(
        name=name,
        date=date_value,
        defaults={
            "time": time_value,
            "place": place,
            "price": price_value,
            "short_description": short_description,
            "source_url": source_url,
        },
    )

    event_categories = []
    for cat_name in category_names:
        cat_name = str(cat_name).strip()
        if cat_name:
            category, _ = Category.objects.get_or_create(name=cat_name)
            event_categories.append(category)
    if event_categories:
        event.categories.set(event_categories)

    return Response(
        {
            "message": "Event created." if created else "Event updated.",
            "event_id": event.id,
            "name": event.name,
            "date": str(event.date),
            "time": event.time.strftime("%H:%M"),
            "place": event.place,
            "price": str(event.price),
            "short_description": event.short_description,
            "categories": [c.name for c in event.categories.all()],
            "source_url": event.source_url,
            "created": created,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )