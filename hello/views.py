import json
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

@csrf_exempt
def add_student(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')

            if not username or not password:
                return JsonResponse({'error': 'Username and password are required'}, status=400)

            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'Username already exists'}, status=400)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            student = Student.objects.create(user=user)

            return JsonResponse({
                'message': 'Student created successfully',
                'student_id': student.id,
                'user_id': user.id
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Category.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Category already exists'}, status=400)

            category = Category.objects.create(name=name)

            return JsonResponse({
                'message': 'Category created successfully',
                'category_id': category.id,
                'name': category.name
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_subject(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            category_id = data.get('category_id')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Subject.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Subject already exists'}, status=400)

            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    return JsonResponse({'error': 'Category not found'}, status=400)

            subject = Subject.objects.create(name=name, category=category)

            return JsonResponse({
                'message': 'Subject created successfully',
                'subject_id': subject.id,
                'name': subject.name,
                'category_id': category.id if category else None,
                'category_name': category.name if category else None
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_subject_interest(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            subject_id = data.get('subject_id')
            interest = data.get('interest')

            if not all([student_id, subject_id, interest]):
                return JsonResponse({'error': 'student_id, subject_id, and interest are required'}, status=400)

            try:
                interest = int(interest)
                if interest not in [1, 2, 3, 4, 5]:
                    return JsonResponse({'error': 'Interest must be between 1 and 5'}, status=400)
            except ValueError:
                return JsonResponse({'error': 'Interest must be a number'}, status=400)

            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return JsonResponse({'error': 'Student not found'}, status=404)

            try:
                subject = Subject.objects.get(id=subject_id)
            except Subject.DoesNotExist:
                return JsonResponse({'error': 'Subject not found'}, status=404)

            student_subject, created = StudentSubject.objects.update_or_create(
                student=student,
                subject=subject,
                defaults={'interest': interest}
            )

            return JsonResponse({
                'message': 'Interest level updated successfully' if not created else 'Interest level set successfully',
                'student_id': student_id,
                'subject_id': subject_id,
                'interest': interest,
                'created': created
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

def get_student_subjects(request, student_id):
    if request.method == 'GET':
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)

        student_subjects = StudentSubject.objects.filter(student=student).select_related('subject__category')

        subjects_data = []
        for ss in student_subjects:
            subject = ss.subject
            subjects_data.append({
                'subject_id': subject.id,
                'name': subject.name,
                'category_id': subject.category.id if subject.category else None,
                'category_name': subject.category.name if subject.category else None,
                'interest': ss.interest,
                'interest_description': dict(StudentSubject.INTEREST_CHOICES)[ss.interest]
            })

        return JsonResponse({
            'student_id': student_id,
            'student_username': student.user.username,
            'subjects': subjects_data,
            'total_subjects': len(subjects_data)
        }, status=200)

    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Category.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Category already exists'}, status=400)

            category = Category.objects.create(name=name)

            return JsonResponse({
                'message': 'Category created successfully',
                'category_id': category.id,
                'name': category.name
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_subject(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            category_id = data.get('category_id')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Subject.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Subject already exists'}, status=400)

            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    return JsonResponse({'error': 'Category not found'}, status=400)

            subject = Subject.objects.create(name=name, category=category)

            return JsonResponse({
                'message': 'Subject created successfully',
                'subject_id': subject.id,
                'name': subject.name,
                'category_id': category.id if category else None,
                'category_name': category.name if category else None
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def scrape_text(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    url = (payload.get("url") or "").strip()
    from_semester = payload.get("fromSemester", 1)
    to_semester = payload.get("toSemester", 4)

    try:
        from_semester = int(from_semester)
        to_semester = int(to_semester)
    except (TypeError, ValueError):
        return JsonResponse({"error": "fromSemester and toSemester must be numbers."}, status=400)

    if from_semester > to_semester:
        return JsonResponse({"error": "fromSemester cannot be greater than toSemester."}, status=400)
    if not url:
        return JsonResponse({"error": "Field 'url' is required."}, status=400)
    if not (url.startswith("http://") or url.startswith("https://")):
        return JsonResponse({"error": "URL must start with http:// or https://."}, status=400)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.HTTPError as e:
            return JsonResponse({"error": f"HTTP error: {e.response.status_code}"}, status=400)
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == max_retries - 1:
                return JsonResponse({"error": f"Failed after {max_retries} attempts: {e}"}, status=400)
            time.sleep(1)
        except requests.RequestException as e:
            return JsonResponse({"error": f"Request failed: {e}"}, status=400)

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
        return JsonResponse(
            {"error": "Ollama Python package is not installed. Install it with: pip install ollama"},
            status=500,
        )

    prompt = (
        "Extract only study subject names from semesters "
        f"{from_semester} to {to_semester} from the provided webpage text. "
        "Do not translate or modify original subject text. "
        "Return strict JSON only in this format: "
        '{"study_subjects": ["subject 1", "subject 2"]}. '
        "No markdown, no explanation.\n\n"
        f"Webpage text:\n{text}"
    )

    try:
        ollama_response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        return JsonResponse({"error": f"Ollama request failed: {exc}"}, status=500)

    raw_content = ollama_response.get("message", {}).get("content", "").strip()

    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

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

    subjects = []
    if isinstance(parsed, dict) and isinstance(parsed.get("study_subjects"), list):
        subjects = [str(item).strip() for item in parsed["study_subjects"] if str(item).strip()]
    else:
        subjects = [
            line.strip("-• \t")
            for line in raw_content.splitlines()
            if line.strip("-• \t")
        ]

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

    return JsonResponse(
        {
            "message": "Scrape and AI extraction completed successfully.",
            "file": str(txt_output_file.relative_to(settings.BASE_DIR)),
            "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
            "characters": len(text),
            "subjects_count": len(subjects),
            "study_subjects": subjects,
        }
    )


@csrf_exempt
def scrape_events(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    url = (payload.get("url") or "").strip()
    model_name = (payload.get("model") or "llama3").strip()
    max_events = payload.get("max_events", 20)
    city = (payload.get("city") or "").strip()

    try:
        max_events = int(max_events)
    except (TypeError, ValueError):
        return JsonResponse({"error": "max_events must be a number."}, status=400)
    if max_events < 1:
        return JsonResponse({"error": "max_events must be at least 1."}, status=400)
    if not url:
        return JsonResponse({"error": "Field 'url' is required."}, status=400)
    if not (url.startswith("http://") or url.startswith("https://")):
        return JsonResponse({"error": "URL must start with http:// or https://."}, status=400)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.HTTPError as e:
            return JsonResponse({"error": f"HTTP error: {e.response.status_code}"}, status=400)
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == max_retries - 1:
                return JsonResponse({"error": f"Failed after {max_retries} attempts: {e}"}, status=400)
            time.sleep(1)
        except requests.RequestException as e:
            return JsonResponse({"error": f"Request failed: {e}"}, status=400)

    soup = BeautifulSoup(response.text, "html.parser")

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import ollama
    except ImportError:
        return JsonResponse(
            {"error": "Ollama Python package is not installed. Install it with: pip install ollama"},
            status=500,
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
            return JsonResponse(
                {"error": f"No event links found for source '{source}' and no saved links are available."},
                status=400,
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
            return JsonResponse({"error": f"Ollama request failed: {exc}"}, status=500)

        parsed = _parse_json_from_model_output(ollama_response.get("message", {}).get("content", ""))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("events"), list):
            return JsonResponse({"error": "Could not parse events JSON from model output."}, status=500)

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
            time=time_value,
            defaults={
                "place": place,
                "price": price_value,
                "short_description": short_description or f"Event: {name}",
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
                "source_url": item.get("source_url"),
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

    return JsonResponse(
        {
            "message": "Event scrape and extraction completed.",
            "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
            "created_events": created_events,
            "updated_events": updated_events,
            "failed_count": len(failed_events),
            "events": saved_events,
            "failed": failed_events,
        }
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