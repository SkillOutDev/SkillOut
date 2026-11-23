"""
Main orchestration for text scraping and subject extraction.
Coordinates workflow across specialized modules.
"""
from pathlib import Path

from django.conf import settings

from .ai_extractor import extract_subjects
from .file_saver import save_scraped_text, save_subjects
from .request_validator import RequestValidator, ScrapeTextError
from .web_scraper import fetch_webpage_text


def process_scrape_text(payload):
    """Validate the request, scrape the page, extract subjects, and save the results."""
    validator = RequestValidator()
    validator.validate_scrape_request(payload)

    url = (payload.get("url") or "").strip()
    from_semester = int(payload.get("fromSemester"))
    to_semester = int(payload.get("toSemester"))

    text = fetch_webpage_text(url)
    output_dir, txt_output_file = save_scraped_text(text)
    subjects = extract_subjects(text, from_semester, to_semester)
    json_output_file = save_subjects(output_dir, url, from_semester, to_semester, subjects)

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
