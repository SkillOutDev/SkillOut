"""
Main orchestration for web scraping and subject extraction.
Coordinates validation, fetching, extraction, and file saving.
"""
from typing import TypedDict

from django.conf import settings

from .ai_extractor import extract_subjects
from .file_saver import save_scraped_text, save_subjects
from .request_validator import RequestValidator
from .web_scraper import fetch_webpage_text


class ScrapeTextResponse(TypedDict):
    """Response structure for scrape_text processing."""
    message: str
    file: str
    json_file: str
    characters: int
    subjects_count: int
    study_subjects: list[str]


def process_scrape_text(payload: dict) -> ScrapeTextResponse:
    """
    Validate the request, scrape the page, extract subjects, and save the results.

    Args:
        payload: Request payload with url, fromSemester, toSemester

    Returns:
        ScrapeTextResponse with results and file locations
    """
    url, from_semester, to_semester = RequestValidator.validate_scrape_request(payload)
    text = fetch_webpage_text(url)
    output_dir, txt_output_file = save_scraped_text(text)
    subjects = extract_subjects(text, from_semester, to_semester)
    json_output_file = save_subjects(
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
