import json
import sys
import types
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from hello.models import Category, Event, Student, StudentSubject, Subject


class ScrapeSemesterValidationTests(TestCase):
	endpoint = "/api/scrape-text/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_requires_from_and_to_semester(self):
		response = self._post({"url": "https://example.com"})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			response.json()["error"],
			"Fields 'fromSemester' and 'toSemester' are required.",
		)

	def test_rejects_when_from_semester_is_greater_than_to_semester(self):
		response = self._post(
			{
				"url": "https://example.com",
				"fromSemester": 5,
				"toSemester": 3,
			}
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			response.json()["error"],
			"fromSemester cannot be greater than toSemester.",
		)

	def test_rejects_semesters_below_one(self):
		response = self._post(
			{
				"url": "https://example.com",
				"fromSemester": 0,
				"toSemester": 3,
			}
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			response.json()["error"],
			"fromSemester and toSemester must be at least 1.",
		)

	def test_rejects_semesters_above_eight(self):
		response = self._post(
			{
				"url": "https://example.com",
				"fromSemester": 1,
				"toSemester": 9,
			}
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			response.json()["error"],
			"fromSemester and toSemester must be at most 8.",
		)


class ScrapeSubjectsResponseTests(TestCase):
	endpoint = "/api/scrape-text/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	@patch("hello.views.requests.get")
	def test_returns_subject_list_for_selected_semester_interval(self, mock_get):
		html = """
		<html><body>
			<h3>1 rudens semestras</h3>
			<p>Matematika</p>
			<h3>2 pavasario semestras</h3>
			<p>Programavimas</p>
			<h3>3 rudens semestras</h3>
			<p>Duomenu bazes</p>
		</body></html>
		"""
		mock_response = MagicMock()
		mock_response.text = html
		mock_response.raise_for_status.return_value = None
		mock_get.return_value = mock_response

		fake_ollama = types.SimpleNamespace(
			chat=lambda **kwargs: {
				"message": {
					"content": json.dumps(
						{
							"study_subjects": [
								"Programavimas",
								"Duomenu bazes",
							]
						}
					)
				}
			}
		)

		with patch.dict(sys.modules, {"ollama": fake_ollama}):
			response = self._post(
				{
					"url": "https://example.com/study-plan",
					"fromSemester": 2,
					"toSemester": 3,
				}
			)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertIsInstance(data["study_subjects"], list)
		self.assertEqual(data["subjects_count"], 2)
		self.assertEqual(
			data["study_subjects"],
			["Programavimas", "Duomenu bazes"],
		)

	@patch("hello.views.requests.get")
	def test_returns_no_results_message_when_subjects_not_found(self, mock_get):
		html = """
		<html><body>
			<h3>4 pavasario semestras</h3>
			<p>Nera dalyku</p>
		</body></html>
		"""
		mock_response = MagicMock()
		mock_response.text = html
		mock_response.raise_for_status.return_value = None
		mock_get.return_value = mock_response

		fake_ollama = types.SimpleNamespace(
			chat=lambda **kwargs: {"message": {"content": '{"study_subjects": []}'}}
		)

		with patch.dict(sys.modules, {"ollama": fake_ollama}):
			response = self._post(
				{
					"url": "https://example.com/study-plan",
					"fromSemester": 4,
					"toSemester": 4,
				}
			)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["study_subjects"], [])
		self.assertEqual(data["subjects_count"], 0)
		self.assertEqual(
			data["message"],
			"No results found for the selected semester range.",
		)


class ScrapeUrlValidationTests(TestCase):
	endpoint = "/api/scrape-text/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_requires_url(self):
		response = self._post({
			"fromSemester": 1,
			"toSemester": 2,
		})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			response.json()["error"],
			"Field 'url' is required.",
		)

	def test_rejects_invalid_url_format(self):
		response = self._post({
			"url": "ftp://example.com",
			"fromSemester": 1,
			"toSemester": 2,
		})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			response.json()["error"],
			"URL must start with http:// or https://.",
		)

	@patch("hello.views.requests.get")
	def test_handles_4xx_error(self, mock_get):
		mock_response = MagicMock()
		http_error = requests.HTTPError("404 Client Error")
		http_error.response = MagicMock()
		http_error.response.status_code = 404
		mock_response.raise_for_status.side_effect = http_error
		mock_get.return_value = mock_response

		response = self._post({
			"url": "https://example.com",
			"fromSemester": 1,
			"toSemester": 2,
		})

		self.assertEqual(response.status_code, 400)
		self.assertIn("HTTP error: 404", response.json()["error"])

	@patch("hello.views.requests.get")
	def test_handles_5xx_error(self, mock_get):
		mock_response = MagicMock()
		http_error = requests.HTTPError("500 Server Error")
		http_error.response = MagicMock()
		http_error.response.status_code = 500
		mock_response.raise_for_status.side_effect = http_error
		mock_get.return_value = mock_response

		response = self._post({
			"url": "https://example.com",
			"fromSemester": 1,
			"toSemester": 2,
		})

		self.assertEqual(response.status_code, 400)
		self.assertIn("HTTP error: 500", response.json()["error"])

	@patch("hello.views.requests.get")
	@patch("hello.views.time.sleep")
	def test_handles_timeout_after_retries(self, mock_sleep, mock_get):
		mock_get.side_effect = requests.Timeout("Request timed out")

		response = self._post({
			"url": "https://example.com",
			"fromSemester": 1,
			"toSemester": 2,
		})

		self.assertEqual(response.status_code, 400)
		self.assertIn("Failed after 3 attempts", response.json()["error"])
		self.assertEqual(mock_get.call_count, 3)
		self.assertEqual(mock_sleep.call_count, 2)  # Sleeps after first two attempts

	@patch("hello.views.requests.get")
	@patch("hello.views.time.sleep")
	def test_handles_connection_error_with_retry_success(self, mock_sleep, mock_get):
		mock_get.side_effect = [
			requests.ConnectionError("Connection failed"),
			requests.ConnectionError("Connection failed"),
			MagicMock(text="<html></html>", raise_for_status=lambda: None)
		]

		fake_ollama = types.SimpleNamespace(
			chat=lambda **kwargs: {"message": {"content": '{"study_subjects": []}'}}
		)

		with patch.dict(sys.modules, {"ollama": fake_ollama}):
			response = self._post({
				"url": "https://example.com",
				"fromSemester": 1,
				"toSemester": 2,
			})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(mock_get.call_count, 3)
		self.assertEqual(mock_sleep.call_count, 2)

	@patch("hello.views.requests.get")
	@patch("hello.views.time.sleep")
	def test_handles_connection_error_retry_fail(self, mock_sleep, mock_get):
		mock_get.side_effect = requests.ConnectionError("Connection failed")

		response = self._post({
			"url": "https://example.com",
			"fromSemester": 1,
			"toSemester": 2,
		})

		self.assertEqual(response.status_code, 400)
		self.assertIn("Failed after 3 attempts", response.json()["error"])
		self.assertEqual(mock_get.call_count, 3)
		self.assertEqual(mock_sleep.call_count, 2)


# AC1: Sistema identifikuoja studijų dalykų, esančių kiekviename semestre pavadinimus.
# (The system identifies study subject names present in each semester.)
class SubjectIdentificationTests(TestCase):
	"""Tests verifying that the scraper correctly identifies subjects per semester."""

	endpoint = "/api/scrape-text/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def _fake_ollama(self, subjects):
		return types.SimpleNamespace(
			chat=lambda **kwargs: {
				"message": {"content": json.dumps({"study_subjects": subjects})}
			}
		)

	@patch("hello.views.requests.get")
	def test_identifies_subjects_from_single_semester(self, mock_get):
		"""Subjects from exactly one requested semester are returned."""
		mock_response = MagicMock()
		mock_response.text = "<html><body><h3>1 semestras</h3><p>Matematika</p></body></html>"
		mock_response.raise_for_status.return_value = None
		mock_get.return_value = mock_response

		with patch.dict(sys.modules, {"ollama": self._fake_ollama(["Matematika"])}):
			response = self._post({
				"url": "https://example.com/plan",
				"fromSemester": 1,
				"toSemester": 1,
			})

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["subjects_count"], 1)
		self.assertIn("Matematika", data["study_subjects"])

	@patch("hello.views.requests.get")
	def test_identifies_subjects_across_multiple_semesters(self, mock_get):
		"""Subjects from a range of semesters are all returned."""
		mock_response = MagicMock()
		mock_response.text = (
			"<html><body>"
			"<h3>2 semestras</h3><p>Fizika</p>"
			"<h3>3 semestras</h3><p>Chemija</p>"
			"<h3>4 semestras</h3><p>Biologija</p>"
			"</body></html>"
		)
		mock_response.raise_for_status.return_value = None
		mock_get.return_value = mock_response

		with patch.dict(sys.modules, {"ollama": self._fake_ollama(["Fizika", "Chemija", "Biologija"])}):
			response = self._post({
				"url": "https://example.com/plan",
				"fromSemester": 2,
				"toSemester": 4,
			})

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["subjects_count"], 3)
		self.assertEqual(data["study_subjects"], ["Fizika", "Chemija", "Biologija"])

	@patch("hello.views.requests.get")
	def test_subject_names_returned_as_list_of_strings(self, mock_get):
		"""Returned study_subjects must be a list of plain strings, not objects."""
		mock_response = MagicMock()
		mock_response.text = "<html><body><p>Programu sistemos</p></body></html>"
		mock_response.raise_for_status.return_value = None
		mock_get.return_value = mock_response

		with patch.dict(sys.modules, {"ollama": self._fake_ollama(["Programu sistemos"])}):
			response = self._post({
				"url": "https://example.com/plan",
				"fromSemester": 1,
				"toSemester": 2,
			})

		self.assertEqual(response.status_code, 200)
		subjects = response.json()["study_subjects"]
		self.assertIsInstance(subjects, list)
		for item in subjects:
			self.assertIsInstance(item, str)

	@patch("hello.views.requests.get")
	def test_response_includes_semester_range_metadata(self, mock_get):
		"""The saved JSON file must contain from_semester and to_semester matching the request."""
		import os
		from django.conf import settings

		mock_response = MagicMock()
		mock_response.text = "<html><body><p>Tinklai</p></body></html>"
		mock_response.raise_for_status.return_value = None
		mock_get.return_value = mock_response

		with patch.dict(sys.modules, {"ollama": self._fake_ollama(["Tinklai"])}):
			response = self._post({
				"url": "https://example.com/plan",
				"fromSemester": 3,
				"toSemester": 5,
			})

		self.assertEqual(response.status_code, 200)
		json_path = os.path.join(settings.BASE_DIR, "scraped_text", "latest_subjects.json")
		with open(json_path, encoding="utf-8") as f:
			saved = json.load(f)
		self.assertEqual(saved["from_semester"], 3)
		self.assertEqual(saved["to_semester"], 5)


# AC2: Sistema neturi sukurti identiško programos įrašo, jei dokumentas sutampa su jau esančiu dalyku.
# (The system must not create a duplicate subject if it already exists in the database.)
class SubjectDeduplicationTests(TestCase):
	"""Tests verifying that importing an already-existing subject does not create duplicates."""

	endpoint = "/api/import-subjects/"
	ADD_SUBJECT_URL = "/add-subject/"

	def setUp(self):
		from hello.models import Category, Subject
		self.category = Category.objects.create(name="IT")
		self.existing_subject = Subject.objects.create(name="Duomenu bazes", category=self.category)

	def _import(self, subjects, model="llama3"):
		return self.client.post(
			self.endpoint,
			data=json.dumps({"study_subjects": subjects, "model": model}),
			content_type="application/json",
		)

	def _fake_ollama(self, category="IT"):
		return types.SimpleNamespace(
			list=lambda: None,
			chat=lambda **kwargs: {
				"message": {"content": json.dumps({"category": category})}
			},
		)

	def test_does_not_create_duplicate_when_subject_name_matches_exactly(self):
		"""Importing a subject with identical name must not create a second DB row."""
		from hello.models import Subject

		count_before = Subject.objects.filter(name="Duomenu bazes").count()

		with patch.dict(sys.modules, {"ollama": self._fake_ollama()}):
			response = self._import(["Duomenu bazes"])

		self.assertEqual(response.status_code, 200)
		count_after = Subject.objects.filter(name="Duomenu bazes").count()
		self.assertEqual(count_before, count_after)

	def test_does_not_create_duplicate_when_subject_name_differs_only_in_case(self):
		"""Subject lookup is case-insensitive; same subject different case must not duplicate."""
		from hello.models import Subject

		with patch.dict(sys.modules, {"ollama": self._fake_ollama()}):
			response = self._import(["duomenu bazes"])

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Subject.objects.filter(name__iexact="duomenu bazes").count(), 1)

	def test_import_reports_unchanged_for_existing_subject_same_category(self):
		"""When subject and category both already exist, action must be 'unchanged'."""
		with patch.dict(sys.modules, {"ollama": self._fake_ollama(category="IT")}):
			response = self._import(["Duomenu bazes"])

		self.assertEqual(response.status_code, 200)
		data = response.json()
		matched = [p for p in data["processed"] if p["subject"].lower() == "duomenu bazes"]
		self.assertTrue(matched, "Subject not found in processed list")
		self.assertEqual(matched[0]["action"], "unchanged")

	def test_new_subject_is_created_when_name_is_different(self):
		"""A subject with a new unique name must be created (no false positive dedup)."""
		from hello.models import Subject

		with patch.dict(sys.modules, {"ollama": self._fake_ollama(category="IT")}):
			response = self._import(["Dirbtinis intelektas"])

		self.assertEqual(response.status_code, 200)
		self.assertTrue(Subject.objects.filter(name="Dirbtinis intelektas").exists())
		data = response.json()
		self.assertEqual(data["created_subjects"], 1)


# AC3: Identifikuoti studijų dalykai turi būti susieti su konkrečiu studentu bei jo susidomėjimo lygiu.
# (Identified subjects must be linked to a specific student along with their interest level.)
class SubjectInterestAssignmentTests(TestCase):
	"""Tests verifying subject-to-student linking and interest level storage."""

	endpoint = "/add-interest/"

	def setUp(self):
		from django.contrib.auth.models import User
		from hello.models import Category, Student, Subject
		self.user = User.objects.create_user(username="teststudent", password="pass")
		self.student = Student.objects.create(user=self.user)
		self.category = Category.objects.create(name="IT")
		self.subject = Subject.objects.create(name="Algoritmika", category=self.category)

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_links_subject_to_student_with_interest_level(self):
		"""POST to add-interest must create a StudentSubject record with correct interest."""
		from hello.models import Student, StudentSubject
		student = Student.objects.get(id=1)  # DEFAULT_STUDENT_ID

		response = self._post({"subject_id": self.subject.id, "interest": 4})

		self.assertEqual(response.status_code, 201)
		self.assertTrue(
			StudentSubject.objects.filter(student=student, subject=self.subject, interest=4).exists()
		)

	def test_interest_level_is_stored_correctly_in_database(self):
		"""The exact interest value sent must be persisted in the DB."""
		from hello.models import Student, StudentSubject
		student = Student.objects.get(id=1)

		self._post({"subject_id": self.subject.id, "interest": 5})

		record = StudentSubject.objects.get(student=student, subject=self.subject)
		self.assertEqual(record.interest, 5)

	def test_updating_interest_does_not_create_duplicate_assignment(self):
		"""Posting the same subject twice with different interest must update, not duplicate."""
		from hello.models import Student, StudentSubject
		student = Student.objects.get(id=1)

		self._post({"subject_id": self.subject.id, "interest": 2})
		self._post({"subject_id": self.subject.id, "interest": 5})

		records = StudentSubject.objects.filter(student=student, subject=self.subject)
		self.assertEqual(records.count(), 1)
		self.assertEqual(records.first().interest, 5)

	def test_rejects_interest_outside_valid_range(self):
		"""Interest values outside 1-5 must be rejected with 400."""
		response_low = self._post({"subject_id": self.subject.id, "interest": 0})
		response_high = self._post({"subject_id": self.subject.id, "interest": 6})

		self.assertEqual(response_low.status_code, 400)
		self.assertEqual(response_high.status_code, 400)

	def test_rejects_assignment_when_subject_does_not_exist(self):
		"""Using a non-existent subject_id must return 404."""
		response = self._post({"subject_id": 99999, "interest": 3})

		self.assertEqual(response.status_code, 404)
		self.assertIn("Subject not found", response.json()["error"])

	def test_student_subjects_endpoint_returns_linked_subject_with_interest(self):
		"""GET student/<id>/subjects/ must return the subject and its interest level."""
		from hello.models import Student, StudentSubject
		student = Student.objects.get(id=1)
		StudentSubject.objects.create(student=student, subject=self.subject, interest=3)

		response = self.client.get(f"/student/{student.id}/subjects/")

		self.assertEqual(response.status_code, 200)
		data = response.json()
		subjects = data["subjects"]
		self.assertTrue(
			any(s["name"] == "Algoritmika" and s["interest"] == 3 for s in subjects),
			f"Expected subject with interest not found in: {subjects}",
		)


# ---------------------------------------------------------------------------
# add_student view tests
# ---------------------------------------------------------------------------
class AddStudentTests(TestCase):
	endpoint = "/add-student/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_creates_student_with_valid_data(self):
		response = self._post({"username": "alice", "password": "secret123"})
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertEqual(data["message"], "Student created successfully")
		self.assertIn("student_id", data)
		self.assertIn("user_id", data)

	def test_rejects_missing_username(self):
		response = self._post({"password": "secret123"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Username and password are required", response.json()["error"])

	def test_rejects_missing_password(self):
		response = self._post({"username": "alice"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Username and password are required", response.json()["error"])

	def test_rejects_duplicate_username(self):
		self._post({"username": "bob", "password": "pass1"})
		response = self._post({"username": "bob", "password": "pass2"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Username already exists", response.json()["error"])

	def test_creates_student_with_optional_fields(self):
		response = self._post({
			"username": "carol",
			"password": "pass",
			"email": "carol@example.com",
			"first_name": "Carol",
			"last_name": "Smith",
		})
		self.assertEqual(response.status_code, 201)
		user = User.objects.get(username="carol")
		self.assertEqual(user.email, "carol@example.com")
		self.assertEqual(user.first_name, "Carol")


# ---------------------------------------------------------------------------
# add_category view tests
# ---------------------------------------------------------------------------
class AddCategoryTests(TestCase):
	endpoint = "/add-category/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_creates_category_successfully(self):
		response = self._post({"name": "Engineering"})
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertEqual(data["message"], "Category created successfully")
		self.assertEqual(data["name"], "Engineering")

	def test_rejects_missing_name(self):
		response = self._post({})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Name is required", response.json()["error"])

	def test_rejects_duplicate_category(self):
		self._post({"name": "IT"})
		response = self._post({"name": "IT"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Category already exists", response.json()["error"])


# ---------------------------------------------------------------------------
# add_subject view tests
# ---------------------------------------------------------------------------
class AddSubjectTests(TestCase):
	endpoint = "/add-subject/"

	def setUp(self):
		self.category = Category.objects.create(name="IT")

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_creates_subject_without_category(self):
		response = self._post({"name": "Algebra"})
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertEqual(data["name"], "Algebra")
		self.assertIsNone(data["category_id"])

	def test_creates_subject_with_valid_category(self):
		response = self._post({"name": "Tinklai", "category_id": self.category.id})
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertEqual(data["category_id"], self.category.id)
		self.assertEqual(data["category_name"], "IT")

	def test_rejects_missing_name(self):
		response = self._post({})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Name is required", response.json()["error"])

	def test_rejects_duplicate_subject(self):
		self._post({"name": "Matematika"})
		response = self._post({"name": "Matematika"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Subject already exists", response.json()["error"])

	def test_rejects_nonexistent_category(self):
		response = self._post({"name": "Fizika", "category_id": 99999})
		self.assertEqual(response.status_code, 400)
		self.assertIn("Category not found", response.json()["error"])


# ---------------------------------------------------------------------------
# update_student_subject_interests (bulk update) tests
# ---------------------------------------------------------------------------
class UpdateSubjectInterestsTests(TestCase):
	endpoint = "/update-interests/"

	def setUp(self):
		self.user = User.objects.create_user(username="student1", password="pass")
		self.student = Student.objects.create(user=self.user)
		self.category = Category.objects.create(name="IT")
		self.subject = Subject.objects.create(name="Programavimas", category=self.category)
		StudentSubject.objects.create(student=self.student, subject=self.subject, interest=1)

	def _put(self, payload):
		return self.client.put(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def test_bulk_update_interest_successfully(self):
		response = self._put({"subjects": [{"subject_id": self.subject.id, "interest": 4}]})
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["updated_count"], 1)
		self.assertEqual(data["failed_count"], 0)
		record = StudentSubject.objects.get(student=self.student, subject=self.subject)
		self.assertEqual(record.interest, 4)

	def test_rejects_empty_subjects_list(self):
		response = self._put({"subjects": []})
		self.assertEqual(response.status_code, 400)
		self.assertIn("subjects", response.json()["error"])

	def test_rejects_missing_subjects_field(self):
		response = self._put({})
		self.assertEqual(response.status_code, 400)

	def test_fails_gracefully_for_nonexistent_subject(self):
		response = self._put({"subjects": [{"subject_id": 99999, "interest": 3}]})
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["failed_count"], 1)
		self.assertIn("Subject not found", data["failed"][0]["error"])

	def test_fails_gracefully_for_invalid_interest_value(self):
		response = self._put({"subjects": [{"subject_id": self.subject.id, "interest": 9}]})
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["failed_count"], 1)

	def test_fails_gracefully_for_missing_student_subject_relation(self):
		new_subject = Subject.objects.create(name="Naujas", category=self.category)
		response = self._put({"subjects": [{"subject_id": new_subject.id, "interest": 3}]})
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["failed_count"], 1)
		self.assertIn("not found", data["failed"][0]["error"])


# ---------------------------------------------------------------------------
# get_student_subjects tests
# ---------------------------------------------------------------------------
class GetStudentSubjectsTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="stu2", password="pass")
		self.student = Student.objects.create(user=self.user)
		self.category = Category.objects.create(name="Math")
		self.subject = Subject.objects.create(name="Kalkulus", category=self.category)
		StudentSubject.objects.create(student=self.student, subject=self.subject, interest=2)

	def test_returns_subjects_for_existing_student(self):
		response = self.client.get(f"/student/{self.student.id}/subjects/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["student_id"], self.student.id)
		self.assertEqual(data["student_username"], "stu2")
		self.assertIsInstance(data["subjects"], list)

	def test_returns_404_for_missing_student(self):
		response = self.client.get("/student/99999/subjects/")
		self.assertEqual(response.status_code, 404)
		self.assertIn("Student not found", response.json()["error"])


# ---------------------------------------------------------------------------
# _parse_event_date helper tests
# ---------------------------------------------------------------------------
class ParseEventDateTests(TestCase):
	def _parse(self, value):
		from hello.views import _parse_event_date
		return _parse_event_date(value)

	def test_iso_format_yyyy_mm_dd(self):
		self.assertEqual(self._parse("2026-03-15"), date(2026, 3, 15))

	def test_slash_format_dd_mm_yyyy(self):
		self.assertEqual(self._parse("15/03/2026"), date(2026, 3, 15))

	def test_english_month_name_with_range(self):
		result = self._parse("May 2-3 2026")
		self.assertEqual(result, date(2026, 5, 2))

	def test_day_month_year_format(self):
		result = self._parse("20 March 2026")
		self.assertEqual(result, date(2026, 3, 20))

	def test_range_with_month_at_end(self):
		result = self._parse("15-17 May 2026")
		self.assertEqual(result, date(2026, 5, 15))

	def test_year_first_format(self):
		result = self._parse("2026 May 22-24")
		self.assertEqual(result, date(2026, 5, 22))

	def test_returns_none_for_unrecognized_format(self):
		self.assertIsNone(self._parse("not a date"))

	def test_returns_none_for_empty_string(self):
		self.assertIsNone(self._parse(""))

	def test_returns_none_for_none(self):
		self.assertIsNone(self._parse(None))

	def test_lithuanian_month_name(self):
		result = self._parse("20 kovo 2026")
		self.assertEqual(result, date(2026, 3, 20))


# ---------------------------------------------------------------------------
# _parse_event_time helper tests
# ---------------------------------------------------------------------------
class ParseEventTimeTests(TestCase):
	def _parse(self, value):
		from hello.views import _parse_event_time
		return _parse_event_time(value)

	def test_hhmm_format(self):
		self.assertEqual(self._parse("14:30"), time(14, 30))

	def test_hhmmss_format(self):
		self.assertEqual(self._parse("09:05:00"), time(9, 5, 0))

	def test_returns_none_for_invalid(self):
		self.assertIsNone(self._parse("not a time"))

	def test_returns_none_for_none(self):
		self.assertIsNone(self._parse(None))

	def test_returns_none_for_empty(self):
		self.assertIsNone(self._parse(""))


# ---------------------------------------------------------------------------
# _parse_event_price helper tests
# ---------------------------------------------------------------------------
class ParseEventPriceTests(TestCase):
	def _parse(self, value):
		from hello.views import _parse_event_price
		return _parse_event_price(value)

	def test_numeric_string(self):
		self.assertEqual(self._parse("25.50"), Decimal("25.50"))

	def test_eur_suffix(self):
		self.assertEqual(self._parse("10 EUR"), Decimal("10.00"))

	def test_euro_sign(self):
		self.assertEqual(self._parse("€15"), Decimal("15.00"))

	def test_free_string(self):
		self.assertEqual(self._parse("free"), Decimal("0.00"))

	def test_empty_string_returns_zero(self):
		self.assertEqual(self._parse(""), Decimal("0.00"))

	def test_none_returns_zero(self):
		self.assertEqual(self._parse(None), Decimal("0.00"))

	def test_comma_decimal(self):
		self.assertEqual(self._parse("12,50"), Decimal("12.50"))

	def test_invalid_returns_none(self):
		self.assertIsNone(self._parse("not-a-price-xyz"))


# ---------------------------------------------------------------------------
# add_event view tests
# ---------------------------------------------------------------------------
class AddEventTests(TestCase):
	endpoint = "/api/events/add/"

	def _post(self, payload):
		return self.client.post(
			self.endpoint,
			data=json.dumps(payload),
			content_type="application/json",
		)

	def _valid_payload(self, **overrides):
		payload = {
			"name": "Test Event",
			"date": "2026-06-01",
			"place": "Vilnius",
			"price": "10.00",
		}
		payload.update(overrides)
		return payload

	def test_creates_event_successfully(self):
		response = self._post(self._valid_payload())
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertEqual(data["name"], "Test Event")
		self.assertTrue(data["created"])

	def test_updates_existing_event(self):
		self._post(self._valid_payload())
		response = self._post(self._valid_payload(price="20.00"))
		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json()["created"])

	def test_rejects_missing_name(self):
		response = self._post({"date": "2026-06-01", "place": "Vilnius"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("name", response.json()["error"].lower())

	def test_rejects_missing_date(self):
		response = self._post({"name": "Event", "place": "Vilnius"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("date", response.json()["error"].lower())

	def test_rejects_missing_place(self):
		response = self._post({"name": "Event", "date": "2026-06-01"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("place", response.json()["error"].lower())

	def test_rejects_invalid_date_format(self):
		response = self._post(self._valid_payload(date="not-a-date"))
		self.assertEqual(response.status_code, 400)
		self.assertIn("date", response.json()["error"].lower())

	def test_creates_event_with_categories(self):
		response = self._post(self._valid_payload(categories=["IT", "Business"]))
		self.assertEqual(response.status_code, 201)
		self.assertIn("IT", response.json()["categories"])

	def test_creates_event_with_source_url(self):
		response = self._post(self._valid_payload(source_url="https://example.com/event"))
		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.json()["source_url"], "https://example.com/event")


# ---------------------------------------------------------------------------
# get_events view tests
# ---------------------------------------------------------------------------
class GetEventsTests(TestCase):
	def setUp(self):
		self.cat = Category.objects.create(name="Tech")
		Event.objects.create(
			name="Conf 2026",
			date=date(2026, 5, 10),
			time=time(10, 0),
			place="Kaunas",
			price=Decimal("0"),
			short_description="A tech conf",
		)

	def test_returns_all_events(self):
		response = self.client.get("/api/events/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["total"], 1)
		self.assertEqual(data["events"][0]["name"], "Conf 2026")

	def test_returns_empty_list_when_no_events(self):
		Event.objects.all().delete()
		response = self.client.get("/api/events/")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["total"], 0)


# ---------------------------------------------------------------------------
# get_event_by_id view tests
# ---------------------------------------------------------------------------
class GetEventByIdTests(TestCase):
	def setUp(self):
		self.event = Event.objects.create(
			name="Single Event",
			date=date(2026, 7, 1),
			time=time(18, 0),
			place="Klaipeda",
			price=Decimal("5.00"),
			short_description="A single event",
		)

	def test_returns_event_by_valid_id(self):
		response = self.client.get(f"/api/events/{self.event.id}/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["name"], "Single Event")
		self.assertEqual(data["place"], "Klaipeda")

	def test_returns_404_for_nonexistent_event(self):
		response = self.client.get("/api/events/99999/")
		self.assertEqual(response.status_code, 404)
		self.assertIn("Event not found", response.json()["error"])


# ---------------------------------------------------------------------------
# filter_events view tests
# ---------------------------------------------------------------------------
class FilterEventsTests(TestCase):
	def setUp(self):
		self.cat = Category.objects.create(name="Music")
		self.e1 = Event.objects.create(
			name="Free Concert",
			date=date(2026, 6, 1),
			time=time(19, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="Free outdoor concert",
		)
		self.e2 = Event.objects.create(
			name="Paid Seminar",
			date=date(2026, 6, 15),
			time=time(10, 0),
			place="Kaunas",
			price=Decimal("50.00"),
			short_description="A paid seminar",
		)

	def test_filter_by_min_price(self):
		response = self.client.get("/api/events/filter/?min_price=10")
		self.assertEqual(response.status_code, 200)
		names = [e["name"] for e in response.json()["events"]]
		self.assertIn("Paid Seminar", names)
		self.assertNotIn("Free Concert", names)

	def test_filter_by_max_price(self):
		response = self.client.get("/api/events/filter/?max_price=5")
		self.assertEqual(response.status_code, 200)
		names = [e["name"] for e in response.json()["events"]]
		self.assertIn("Free Concert", names)
		self.assertNotIn("Paid Seminar", names)

	def test_filter_by_city(self):
		response = self.client.get("/api/events/filter/?city=Vilnius")
		self.assertEqual(response.status_code, 200)
		names = [e["name"] for e in response.json()["events"]]
		self.assertIn("Free Concert", names)
		self.assertNotIn("Paid Seminar", names)

	def test_filter_by_date_range(self):
		response = self.client.get("/api/events/filter/?start_date=2026-06-10&end_date=2026-06-20")
		self.assertEqual(response.status_code, 200)
		names = [e["name"] for e in response.json()["events"]]
		self.assertIn("Paid Seminar", names)
		self.assertNotIn("Free Concert", names)

	def test_rejects_inverted_price_range(self):
		response = self.client.get("/api/events/filter/?min_price=100&max_price=10")
		self.assertEqual(response.status_code, 400)
		self.assertIn("min_price", response.json()["error"])

	def test_rejects_inverted_date_range(self):
		response = self.client.get("/api/events/filter/?start_date=2026-07-01&end_date=2026-06-01")
		self.assertEqual(response.status_code, 400)
		self.assertIn("start_date", response.json()["error"])

	def test_rejects_inverted_time_range(self):
		response = self.client.get("/api/events/filter/?start_time=20:00&end_time=09:00")
		self.assertEqual(response.status_code, 400)
		self.assertIn("start_time", response.json()["error"])

	def test_no_filters_returns_all(self):
		response = self.client.get("/api/events/filter/")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["total"], 2)


# ---------------------------------------------------------------------------
# purge_ended_events view tests
# ---------------------------------------------------------------------------
class PurgeEndedEventsTests(TestCase):
	def test_deletes_past_events(self):
		Event.objects.create(
			name="Old Event",
			date=date(2020, 1, 1),
			time=time(10, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="Past event",
		)
		Event.objects.create(
			name="Future Event",
			date=date(2030, 1, 1),
			time=time(10, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="Future event",
		)
		response = self.client.delete("/api/events/purge-ended/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["deleted_count"], 1)
		deleted_names = [e["name"] for e in data["deleted_events"]]
		self.assertIn("Old Event", deleted_names)
		self.assertTrue(Event.objects.filter(name="Future Event").exists())

	def test_returns_zero_when_no_ended_events(self):
		Event.objects.create(
			name="Future Only",
			date=date(2030, 6, 1),
			time=time(10, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="Future",
		)
		response = self.client.delete("/api/events/purge-ended/")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["deleted_count"], 0)


# ---------------------------------------------------------------------------
# get_events_for_student_categories view tests
# ---------------------------------------------------------------------------
class GetEventsForStudentCategoriesTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="evtstudent", password="pass")
		self.student = Student.objects.create(user=self.user)
		self.cat = Category.objects.create(name="IT")
		self.subject = Subject.objects.create(name="Programavimas", category=self.cat)
		self.event = Event.objects.create(
			name="IT Conference",
			date=date(2026, 9, 1),
			time=time(10, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="IT event",
		)
		self.event.categories.add(self.cat)

	def test_returns_matched_events_when_student_has_rated_subjects(self):
		StudentSubject.objects.create(student=self.student, subject=self.subject, interest=3)
		response = self.client.get(f"/api/events/student/{self.student.id}/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["mode"], "matched-only")
		names = [e["name"] for e in data["events"]]
		self.assertIn("IT Conference", names)

	def test_returns_default_events_when_student_has_no_subjects(self):
		response = self.client.get(f"/api/events/student/{self.student.id}/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["mode"], "default")

	def test_returns_default_events_when_all_interests_are_zero(self):
		StudentSubject.objects.create(student=self.student, subject=self.subject, interest=None)
		response = self.client.get(f"/api/events/student/{self.student.id}/")
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["mode"], "default")

	def test_returns_404_for_nonexistent_student(self):
		response = self.client.get("/api/events/student/99999/")
		self.assertEqual(response.status_code, 404)
		self.assertIn("Student not found", response.json()["error"])


# ---------------------------------------------------------------------------
# SD-78: use student interest levels for event sorting
# ---------------------------------------------------------------------------
class SD78InterestSortingTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="sd78_user", password="pass")
		self.student = Student.objects.create(user=self.user)

		self.cat_high = Category.objects.create(name="High Interest")
		self.cat_low = Category.objects.create(name="Low Interest")
		self.cat_other = Category.objects.create(name="Other")

		self.subj_high = Subject.objects.create(name="Databases", category=self.cat_high)
		self.subj_low = Subject.objects.create(name="Art Basics", category=self.cat_low)

		StudentSubject.objects.create(student=self.student, subject=self.subj_high, interest=5)
		StudentSubject.objects.create(student=self.student, subject=self.subj_low, interest=2)

		# Newer low-interest event: should not outrank high-interest event in SD-78 logic.
		self.low_event = Event.objects.create(
			name="Low Priority Expo",
			date=date(2026, 10, 10),
			time=time(18, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="Low-interest category event",
		)
		self.low_event.categories.add(self.cat_low)

		self.high_event = Event.objects.create(
			name="High Priority Meetup",
			date=date(2026, 9, 1),
			time=time(10, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="High-interest category event",
		)
		self.high_event.categories.add(self.cat_high)

		self.unmatched_event = Event.objects.create(
			name="Unmatched Event",
			date=date(2026, 11, 1),
			time=time(12, 0),
			place="Kaunas",
			price=Decimal("0"),
			short_description="No matching student category",
		)
		self.unmatched_event.categories.add(self.cat_other)

	def test_orders_matched_events_by_interest_descending(self):
		response = self.client.get(f"/api/events/student/{self.student.id}/")
		self.assertEqual(response.status_code, 200)

		data = response.json()
		self.assertEqual(data["mode"], "matched")

		names = [item["name"] for item in data["events"]]
		self.assertEqual(names, ["High Priority Meetup", "Low Priority Expo"])

	def test_excludes_unmatched_categories_in_matched_mode(self):
		response = self.client.get(f"/api/events/student/{self.student.id}/")
		self.assertEqual(response.status_code, 200)

		names = [item["name"] for item in response.json()["events"]]
		self.assertNotIn("Unmatched Event", names)


# ---------------------------------------------------------------------------
# Model __str__ tests
# ---------------------------------------------------------------------------
class ModelStrTests(TestCase):
	def test_category_str(self):
		cat = Category.objects.create(name="Science")
		self.assertEqual(str(cat), "Science")

	def test_subject_str(self):
		cat = Category.objects.create(name="IT")
		subj = Subject.objects.create(name="Algorithms", category=cat)
		self.assertIn("Algorithms", str(subj))

	def test_event_str(self):
		event = Event.objects.create(
			name="Test Event",
			date=date(2026, 5, 1),
			time=time(9, 0),
			place="Vilnius",
			price=Decimal("0"),
			short_description="",
		)
		self.assertEqual(str(event), "Test Event")

	def test_student_str(self):
		user = User.objects.create_user(username="strtest", password="pass")
		student = Student.objects.create(user=user)
		self.assertIn("strtest", str(student))
