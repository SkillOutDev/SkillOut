import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from rest_framework import status


class ScrapeTextError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def _normalize_subject_names(raw_subjects):
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
    }

    for item in raw_subjects:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        compact = value.replace(" ", "")
        if value in skip_tokens:
            continue
        if compact.startswith('study_subjects":[') or compact.startswith("study_subjects:["):
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


def _validate_scrape_request(payload):
    url = (payload.get("url") or "").strip()
    if "fromSemester" not in payload or "toSemester" not in payload:
        raise ScrapeTextError(
            "Fields 'fromSemester' and 'toSemester' are required.",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        from_semester = int(payload.get("fromSemester"))
        to_semester = int(payload.get("toSemester"))
    except (TypeError, ValueError):
        raise ScrapeTextError(
            "fromSemester and toSemester must be numbers.",
            status.HTTP_400_BAD_REQUEST,
        )

    if from_semester < 1 or to_semester < 1:
        raise ScrapeTextError(
            "fromSemester and toSemester must be at least 1.",
            status.HTTP_400_BAD_REQUEST,
        )
    if from_semester > 8 or to_semester > 8:
        raise ScrapeTextError(
            "fromSemester and toSemester must be at most 8.",
            status.HTTP_400_BAD_REQUEST,
        )
    if from_semester > to_semester:
        raise ScrapeTextError(
            "fromSemester cannot be greater than toSemester.",
            status.HTTP_400_BAD_REQUEST,
        )
    if not url:
        raise ScrapeTextError(
            "Field 'url' is required.",
            status.HTTP_400_BAD_REQUEST,
        )
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ScrapeTextError(
            "URL must start with http:// or https://.",
            status.HTTP_400_BAD_REQUEST,
        )

    return url, from_semester, to_semester


def _fetch_webpage_text(url):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.HTTPError as exc:
            raise ScrapeTextError(
                f"HTTP error: {exc.response.status_code}",
                status.HTTP_400_BAD_REQUEST,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == max_retries - 1:
                raise ScrapeTextError(
                    f"Failed after {max_retries} attempts: {exc}",
                    status.HTTP_400_BAD_REQUEST,
                )
            time.sleep(1)
        except requests.RequestException as exc:
            raise ScrapeTextError(
                f"Request failed: {exc}",
                status.HTTP_400_BAD_REQUEST,
            )

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.extract()
    return soup.get_text(separator=" ", strip=True)[:60000]


def _build_extraction_prompt(text, from_semester, to_semester):
    return (
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


def _extract_subjects(text, from_semester, to_semester):
    try:
        import ollama
    except ImportError as exc:
        raise ScrapeTextError(
            "Ollama Python package is not installed. Install it with: pip install ollama",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    prompt = _build_extraction_prompt(text, from_semester, to_semester)
    try:
        ollama_response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "top_p": 0.1},
        )
    except Exception as exc:
        raise ScrapeTextError(
            f"Ollama request failed: {exc}",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    raw_content = ollama_response.get("message", {}).get("content", "").strip()
    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

    return _extract_subject_names_from_ollama_output(raw_content)


def _save_scraped_text(text):
    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_output_file = output_dir / "latest_scrape.txt"
    txt_output_file.write_text(text, encoding="utf-8")
    return output_dir, txt_output_file


def _save_subjects(output_dir, url, from_semester, to_semester, subjects):
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
    return json_output_file


def process_scrape_text(payload):
    """Validate the request, scrape the page, extract subjects, and save the results."""
    url, from_semester, to_semester = _validate_scrape_request(payload)
    text = _fetch_webpage_text(url)
    output_dir, txt_output_file = _save_scraped_text(text)
    subjects = _extract_subjects(text, from_semester, to_semester)
    json_output_file = _save_subjects(
        output_dir, url, from_semester, to_semester, subjects
    )

    result_message = "Scrape and AI extraction completed successfully."
    if not subjects:
        result_message = "No results found for the selected semester range."

    return {
        "message": result_message,
        "file": str(txt_output_file.relative_to(settings.BASE_DIR)),
        "json_file": str(json_output_file.relative_to(settings.BASE_DIR)),
        "characters": len(text),
        "subjects_count": len(subjects),
        "study_subjects": subjects,
    }
