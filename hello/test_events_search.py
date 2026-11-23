from datetime import date, time

import pytest
from django.contrib.auth.models import User

from hello.models import Category, Event, Student, StudentSubject, Subject
from hello.services.events_search import (
    build_student_category_interest_map,
    get_events_similar_to_student_subjects,
    search_events_by_subject_category,
)


@pytest.fixture
def search_data(db):
    it = Category.objects.create(name=" IT ")
    it_event_category = Category.objects.create(name="it")
    art = Category.objects.create(name="Art")
    subject = Subject.objects.create(name="Programming", category=it)
    student = Student.objects.create(user=User.objects.create_user(username="search-student"))

    def event(name, day, category):
        result = Event.objects.create(
            name=name,
            date=date(2026, 6, day),
            time=time(12, 0),
            place="Vilnius",
            price=0,
            short_description="",
        )
        result.categories.add(category)
        return result

    return {
        "it": it,
        "art": art,
        "subject": subject,
        "student": student,
        "older_it": event("Older IT", 1, it_event_category),
        "newer_it": event("Newer IT", 2, it_event_category),
        "art_event": event("Art event", 3, art),
    }


@pytest.mark.parametrize("subject_input", ["instance", "id", "name"])
def test_search_resolves_subject_and_matches_normalized_categories(search_data, subject_input):
    subject = search_data["subject"]
    inputs = {"instance": subject, "id": subject.id, "name": "  pROGRAMMING  "}

    assert search_events_by_subject_category(inputs[subject_input]) == [
        search_data["newer_it"],
        search_data["older_it"],
    ]


@pytest.mark.parametrize("subject_input", [None, 99999, "not found", []])
def test_search_returns_empty_for_unresolvable_subject(search_data, subject_input):
    assert search_events_by_subject_category(subject_input) == []


def test_search_returns_empty_for_subject_without_category(search_data):
    subject = Subject.objects.create(name="Uncategorized", category=None)

    assert search_events_by_subject_category(subject) == []


def test_interest_map_uses_highest_rating_and_skips_unusable_subjects(search_data):
    student = search_data["student"]
    for name, category, interest in [
        ("Programming", search_data["it"], 2),
        ("Databases", search_data["it"], 5),
        ("Drawing", search_data["art"], 0),
        ("No rating", search_data["art"], None),
        ("No category", None, 4),
        ("Blank category", Category.objects.create(name="   "), 4),
    ]:
        subject = search_data["subject"] if name == "Programming" else Subject.objects.create(
            name=name, category=category
        )
        StudentSubject.objects.create(student=student, subject=subject, interest=interest)

    assert build_student_category_interest_map(student) == {"it": 5}


def test_similar_events_rank_by_interest_then_newest(search_data):
    student = search_data["student"]
    art_subject = Subject.objects.create(name="Drawing", category=search_data["art"])
    StudentSubject.objects.create(student=student, subject=search_data["subject"], interest=5)
    StudentSubject.objects.create(student=student, subject=art_subject, interest=2)
    search_data["older_it"].categories.add(search_data["art"])
    Event.objects.create(
        name="Uncategorized",
        date=date(2026, 6, 4),
        time=time(12, 0),
        place="Vilnius",
        price=0,
        short_description="",
    )

    events, categories = get_events_similar_to_student_subjects(student)

    assert events == [search_data["newer_it"], search_data["older_it"], search_data["art_event"]]
    assert categories == ["art", "it"]


def test_similar_events_without_rated_subjects_returns_empty(search_data):
    assert get_events_similar_to_student_subjects(search_data["student"]) == ([], [])
