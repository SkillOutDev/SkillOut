import json
import time
from datetime import datetime
from pathlib import Path

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


class AddSubjectRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    category_id = serializers.IntegerField(required=False, allow_null=True)


class AddSubjectInterestRequestSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    interest = serializers.IntegerField(min_value=1, max_value=5)


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
        "study_subjects",
    }

    for item in raw_subjects:
        value = str(item).strip()
        if not value:
            continue

        value = value.replace("\\", "").strip()
        value = value.strip(',').strip()
        value = value.strip('"').strip()
        value = value.strip(',').strip()
        compact = value.replace(" ", "")

        if not value or value.lower() in skip_tokens:
            continue
        if value in skip_tokens:
            continue
        if compact.startswith("study_subjects\":[") or compact.startswith("study_subjects:["):
            continue

        key = value.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

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
    request=GetStudentSubjectsPathSerializer,
    responses={200: StudentSubjectsResponseSerializer, 404: serializers.DictField()},
)
@api_view(["GET"])
def get_student_subjects(request, student_id):
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

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
    from_semester = payload.get("fromSemester", 1)
    to_semester = payload.get("toSemester", 4)

    try:
        from_semester = int(from_semester)
        to_semester = int(to_semester)
    except (TypeError, ValueError):
        return Response({"error": "fromSemester and toSemester must be numbers."}, status=status.HTTP_400_BAD_REQUEST)

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

    return Response(
        {
            "message": "Scrape and AI extraction completed successfully.",
            "file": str(txt_output_file.relative_to(settings.BASE_DIR)),
            "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
            "characters": len(text),
            "subjects_count": len(subjects),
            "study_subjects": subjects,
        }
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
                return Response({"error": f"Failed after {max_retries} attempts: {e}"}, status=status.HTTP_400_BAD_REQUEST)
            time.sleep(1)
        except requests.RequestException as e:
            return Response({"error": f"Request failed: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.extract()
    text = soup.get_text(separator=" ", strip=True)[:60000]

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
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        return Response({"error": f"Ollama request failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    raw_content = ollama_response.get("message", {}).get("content", "").strip()
    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

    subjects = _extract_subject_names_from_ollama_output(raw_content)
    if not subjects:
        return Response({"error": "No subjects extracted from the provided URL."}, status=status.HTTP_400_BAD_REQUEST)

    created_categories = 0
    created_subjects = 0
    linked_subjects = 0
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
            elif subject.category_id != category.id:
                subject.category = category
                subject.save(update_fields=["category"])

            student_subject, created_link = StudentSubject.objects.get_or_create(
                student=student,
                subject=subject,
                defaults={"interest": None},
            )
            if not created_link and student_subject.interest is None:
                linked_subjects += 1
            elif created_link:
                linked_subjects += 1

            processed.append(
                {
                    "subject": subject.name,
                    "category": category.name,
                    "student_id": student.id,
                    "interest": student_subject.interest,
                }
            )
        except Exception as exc:
            failed.append({"subject": subject_name, "error": str(exc)})

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)
    combined_output_file = output_dir / "latest_subjects_with_categories.json"
    combined_output_file.write_text(
        json.dumps(
            {
                "url": url,
                "from_semester": from_semester,
                "to_semester": to_semester,
                "student_id": student.id,
                "model": model,
                "processed": processed,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return Response(
        {
            "message": "Scrape, import, and student-subject assignment completed.",
            "student_id": student.id,
            "created_categories": created_categories,
            "created_subjects": created_subjects,
            "linked_subjects": linked_subjects,
            "failed_count": len(failed),
            "processed": processed,
            "failed": failed,
            "json_file": str(combined_output_file.relative_to(settings.BASE_DIR)),
        },
        status=status.HTTP_200_OK,
    )