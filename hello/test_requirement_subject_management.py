import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from hello.models import Category, Student, StudentSubject, Subject

ADD_CATEGORY_ENDPOINT = "/add-category/"
ADD_SUBJECT_ENDPOINT = "/api/add-subject/"
ADD_INTEREST_ENDPOINT = "/api/add-interest/"
UPDATE_INTERESTS_ENDPOINT = "/update-interests/"
SCRAPE_TEXT_ENDPOINT = "/api/scrape-text/"


def _subject_payload(**overrides):
    payload = {
        "name": "Programavimas",
        "category_id": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_sd_t118_create_new_category(client):
    response = client.post(
        ADD_CATEGORY_ENDPOINT,
        data=json.dumps({"name": "Informatika"}),
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Informatika"
    assert "category_id" in body


@pytest.mark.django_db
def test_sd_t113_add_new_study_subject(client):
    category = Category.objects.create(name="Technologijos")

    response = client.post(
        ADD_SUBJECT_ENDPOINT,
        data=json.dumps(_subject_payload(name="Dirbtinis intelektas", category_id=category.id)),
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Dirbtinis intelektas"
    assert body["category_id"] == category.id
    assert body["category_name"] == "Technologijos"


@pytest.mark.django_db
def test_sd_t114_add_existing_study_subject_returns_error(client):
    category = Category.objects.create(name="Informatika")
    Subject.objects.create(name="Programavimas", category=category)

    response = client.post(
        ADD_SUBJECT_ENDPOINT,
        data=json.dumps(_subject_payload(name="Programavimas", category_id=category.id)),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Subject already exists"


@pytest.mark.django_db
def test_sd_t112_get_subject_list_with_categories(client):
    it = Category.objects.create(name="IT")
    math = Category.objects.create(name="Matematika")
    Subject.objects.create(name="Algoritmai", category=it)
    Subject.objects.create(name="Diskrecioji matematika", category=math)

    user = User.objects.create_user(username="studentas", password="pass123")
    student = Student.objects.create(user=user)

    response = client.get(f"/api/student/{student.id}/subjects/")

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == student.id
    assert body["student_username"] == "studentas"
    assert body["total_subjects"] == 2
    assert isinstance(body["subjects"], list)

    names_and_categories = {(item["name"], item["category_name"]) for item in body["subjects"]}
    assert ("Algoritmai", "IT") in names_and_categories
    assert ("Diskrecioji matematika", "Matematika") in names_and_categories


@pytest.mark.django_db
def test_sd_t119_create_student_subject_interest_relation(client):
    subject = Subject.objects.create(name="Programavimo pagrindai")

    response = client.post(
        ADD_INTEREST_ENDPOINT,
        data=json.dumps({"subject_id": subject.id, "interest": 4}),
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subject_id"] == subject.id
    assert body["interest"] == 4
    assert body["created"] is True

    relation = StudentSubject.objects.get(subject=subject)
    assert relation.interest == 4


@pytest.mark.django_db
def test_sd_t115_add_subject_with_invalid_category_number(client):
    response = client.post(
        ADD_SUBJECT_ENDPOINT,
        data=json.dumps(_subject_payload(name="Statistika", category_id=99999)),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Category not found"


@pytest.mark.django_db
def test_sd_t116_update_interest_with_invalid_data(client):
    subject = Subject.objects.create(name="Duomenu analize")

    create_response = client.post(
        ADD_INTEREST_ENDPOINT,
        data=json.dumps({"subject_id": subject.id, "interest": 3}),
        content_type="application/json",
    )
    assert create_response.status_code == 201

    response = client.put(
        UPDATE_INTERESTS_ENDPOINT,
        data=json.dumps({"subjects": [{"subject_id": subject.id, "interest": 9}]}),
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated_count"] == 0
    assert body["failed_count"] == 1
    assert body["failed"][0]["error"] == "Interest must be between 1 and 5"


@pytest.mark.django_db
def test_sd_t3_update_interest_with_valid_data_1_to_5(client):
    subject = Subject.objects.create(name="Operacines sistemos")

    create_response = client.post(
        ADD_INTEREST_ENDPOINT,
        data=json.dumps({"subject_id": subject.id, "interest": 2}),
        content_type="application/json",
    )
    assert create_response.status_code == 201

    response = client.put(
        UPDATE_INTERESTS_ENDPOINT,
        data=json.dumps({"subjects": [{"subject_id": subject.id, "interest": 5}]}),
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated_count"] == 1
    assert body["failed_count"] == 0
    assert body["updated"][0]["subject_id"] == subject.id
    assert body["updated"][0]["interest"] == 5

    relation = StudentSubject.objects.get(subject=subject)
    assert relation.interest == 5


@pytest.mark.django_db
def test_sd_t120_interest_is_null_when_not_selected(client):
    category = Category.objects.create(name="Inzinerija")
    Subject.objects.create(name="Signalu apdorojimas", category=category)

    user = User.objects.create_user(username="null_interest_student", password="pass123")
    student = Student.objects.create(user=user)

    response = client.get(f"/api/student/{student.id}/subjects/")

    assert response.status_code == 200
    body = response.json()
    subject_row = next(item for item in body["subjects"] if item["name"] == "Signalu apdorojimas")
    assert subject_row["interest"] is None
    assert subject_row["interest_description"] is None


@pytest.mark.django_db
def test_sd_t117_empty_or_invalid_ai_service_response(client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = "<html><body><p>Studiju planas</p></body></html>"

    fake_ollama_empty = types.SimpleNamespace(
        chat=lambda **kwargs: {"message": {"content": ""}}
    )

    with patch("hello.views.requests.get", return_value=mock_response), patch.dict(
        sys.modules,
        {"ollama": fake_ollama_empty},
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            SCRAPE_TEXT_ENDPOINT,
            data=json.dumps({"url": "https://example.com", "fromSemester": 1, "toSemester": 2}),
            content_type="application/json",
        )

    assert response.status_code == 200
    body = response.json()
    assert body["study_subjects"] == []
    assert body["subjects_count"] == 0
    assert body["message"] == "No results found for the selected semester range."

    fake_ollama_invalid = types.SimpleNamespace(
        chat=lambda **kwargs: {"message": {"content": "nevalidus atsakas be json"}}
    )

    with patch("hello.views.requests.get", return_value=mock_response), patch.dict(
        sys.modules,
        {"ollama": fake_ollama_invalid},
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        invalid_response = client.post(
            SCRAPE_TEXT_ENDPOINT,
            data=json.dumps({"url": "https://example.com", "fromSemester": 1, "toSemester": 2}),
            content_type="application/json",
        )

    assert invalid_response.status_code == 200
    invalid_body = invalid_response.json()
    assert isinstance(invalid_body["study_subjects"], list)
