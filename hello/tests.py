import json
import sys
import types
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase


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
