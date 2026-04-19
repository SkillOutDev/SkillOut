import json
import types
from unittest.mock import MagicMock, patch

import pytest
import requests


@pytest.mark.django_db
def test_requires_url_with_http_or_https_scheme(client):
    response = client.post(
        "/api/scrape-text/",
        data=json.dumps(
            {
                "url": "ftp://example.com/study-plan",
                "fromSemester": 1,
                "toSemester": 2,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "URL must start with http:// or https://."


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["http://example.com/plan", "https://example.com/plan"])
def test_accepts_http_and_https_urls(client, url):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = "<html><body><h3>1 semestras</h3><p>Matematika</p></body></html>"

    fake_ollama = types.SimpleNamespace(
        chat=lambda **kwargs: {
            "message": {"content": json.dumps({"study_subjects": ["Matematika"]})}
        }
    )

    with patch("hello.views.requests.get", return_value=mock_response), patch.dict(
        "sys.modules", {"ollama": fake_ollama}
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps({"url": url, "fromSemester": 1, "toSemester": 1}),
            content_type="application/json",
        )

    assert response.status_code == 200
    assert response.json()["study_subjects"] == ["Matematika"]


@pytest.mark.django_db
def test_returns_subjects_list_when_scrape_and_analysis_succeeds(client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = (
        "<html><body>"
        "<h3>2 semestras</h3><p>Programavimas</p>"
        "<h3>3 semestras</h3><p>Duomenu bazes</p>"
        "</body></html>"
    )

    fake_ollama = types.SimpleNamespace(
        chat=lambda **kwargs: {
            "message": {
                "content": json.dumps(
                    {
                        "study_subjects": [
                            "Programavimas",
                            "",
                            "Duomenu bazes",
                            "   ",
                        ]
                    }
                )
            }
        }
    )

    with patch("hello.views.requests.get", return_value=mock_response), patch.dict(
        "sys.modules", {"ollama": fake_ollama}
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps(
                {
                    "url": "https://example.com/plan",
                    "fromSemester": 2,
                    "toSemester": 3,
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["study_subjects"] == ["Programavimas", "Duomenu bazes"]
    assert data["subjects_count"] == 2
    assert all(isinstance(item, str) and item.strip() for item in data["study_subjects"])


@pytest.mark.django_db
def test_returns_empty_subjects_when_none_found(client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = "<html><body><p>Nera dalyku</p></body></html>"

    fake_ollama = types.SimpleNamespace(
        chat=lambda **kwargs: {"message": {"content": json.dumps({"study_subjects": []})}}
    )

    with patch("hello.views.requests.get", return_value=mock_response), patch.dict(
        "sys.modules", {"ollama": fake_ollama}
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps(
                {
                    "url": "https://example.com/plan",
                    "fromSemester": 1,
                    "toSemester": 1,
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 200
    assert response.json()["study_subjects"] == []


@pytest.mark.django_db
@pytest.mark.parametrize("status_code", [404, 500])
def test_returns_http_error_message_when_page_is_unreachable_by_http_status(client, status_code):
    mock_response = MagicMock()
    http_error = requests.HTTPError(f"{status_code} Error")
    http_error.response = MagicMock()
    http_error.response.status_code = status_code
    mock_response.raise_for_status.side_effect = http_error

    with patch("hello.views.requests.get", return_value=mock_response):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps(
                {
                    "url": "https://example.com/plan",
                    "fromSemester": 1,
                    "toSemester": 1,
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert response.json()["error"] == f"HTTP error: {status_code}"


@pytest.mark.django_db
def test_returns_failed_after_3_attempts_message(client):
    with patch("hello.views.requests.get", side_effect=requests.Timeout("Request timed out")) as mock_get, patch(
        "hello.views.time.sleep"
    ) as mock_sleep:
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps(
                {
                    "url": "https://example.com/plan",
                    "fromSemester": 1,
                    "toSemester": 1,
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert "Failed after 3 attempts" in response.json()["error"]
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.django_db
def test_returns_request_failed_message_for_generic_request_exception(client):
    with patch(
        "hello.views.requests.get", side_effect=requests.RequestException("network exploded")
    ):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps(
                {
                    "url": "https://example.com/plan",
                    "fromSemester": 1,
                    "toSemester": 1,
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert response.json()["error"] == "Request failed: network exploded"


@pytest.mark.django_db
def test_returns_ollama_request_failed_message_when_analysis_fails(client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = "<html><body><p>Some content</p></body></html>"

    fake_ollama = types.SimpleNamespace(
        chat=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("model offline"))
    )

    with patch("hello.views.requests.get", return_value=mock_response), patch.dict(
        "sys.modules", {"ollama": fake_ollama}
    ), patch("hello.views.Path.mkdir"), patch("hello.views.Path.write_text"):
        response = client.post(
            "/api/scrape-text/",
            data=json.dumps(
                {
                    "url": "https://example.com/plan",
                    "fromSemester": 1,
                    "toSemester": 1,
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 500
    assert "Ollama request failed: model offline" == response.json()["error"]
