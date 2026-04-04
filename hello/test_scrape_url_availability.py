import json
import types
import pytest
import requests
from unittest.mock import MagicMock, patch


@pytest.mark.django_db
def test_analysis_starts_when_url_returns_http_200(client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = "<html><body><p>Semester 1: Matematika</p></body></html>"

    fake_ollama = types.SimpleNamespace(
        chat=lambda **kwargs: {
            "message": {
                "content": json.dumps(
                    {"study_subjects": ["Matematika"]}
                )
            }
        }
    )

    with patch("hello.views.requests.get", return_value=mock_response) as mock_get, patch.dict(
        "sys.modules",
        {"ollama": fake_ollama},
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps({"url": "https://example.com", "fromSemester": 1, "toSemester": 1}),
            content_type="application/json",
        )

    assert response.status_code == 200
    assert "error" not in response.json()
    assert mock_get.call_count == 1
    assert response.json()["study_subjects"] == ["Matematika"]


@pytest.mark.django_db
@pytest.mark.parametrize("status_code", [404, 500])
def test_system_handles_http_error(client, status_code):
    mock_response = MagicMock()
    http_error = requests.HTTPError(f"{status_code} Error")
    http_error.response = MagicMock()
    http_error.response.status_code = status_code
    mock_response.raise_for_status.side_effect = http_error

    with patch("hello.views.requests.get", return_value=mock_response):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps({"url": "https://example.com", "fromSemester": 1, "toSemester": 1}),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert f"HTTP error: {status_code}" in response.json()["error"]


@pytest.mark.django_db
def test_system_retries_on_connection_error_and_timeout(client):
    mock_get = patch("hello.views.requests.get").start()
    mock_get.side_effect = [
        requests.ConnectionError("Connection failed"),
        requests.Timeout("Request timed out"),
        MagicMock(text="<html><body>OK</body></html>", raise_for_status=MagicMock(return_value=None)),
    ]

    fake_ollama = types.SimpleNamespace(
        chat=lambda **kwargs: {"message": {"content": json.dumps({"study_subjects": ["OK"]})}}
    )

    with patch.dict("sys.modules", {"ollama": fake_ollama}), patch("hello.views.time.sleep") as mock_sleep, patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps({"url": "https://example.com", "fromSemester": 1, "toSemester": 1}),
            content_type="application/json",
        )

    patch.stopall()

    assert response.status_code == 200
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
    assert response.json()["study_subjects"] == ["OK"]


@pytest.mark.django_db
def test_system_returns_error_after_three_failed_attempts(client):
    with patch("hello.views.requests.get", side_effect=requests.Timeout("Request timed out")) as mock_get, patch("hello.views.time.sleep") as mock_sleep:
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps({"url": "https://example.com", "fromSemester": 1, "toSemester": 1}),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert "Failed after 3 attempts" in response.json()["error"]
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
