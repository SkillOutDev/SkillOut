"""
File I/O operations for saving scrape results.
Handles both text and JSON output files.
"""
import json
from pathlib import Path

from django.conf import settings

from .constants import (
    JSON_INDENT,
    JSON_KEY_STUDY_SUBJECTS,
    JSON_KEY_URL,
    OUTPUT_DIR,
    OUTPUT_FILE_JSON,
    OUTPUT_FILE_TEXT,
)


def save_scraped_text(text: str) -> tuple[Path, Path]:
    """
    Save scraped webpage text to file.

    Args:
        text: Text content to save

    Returns:
        Tuple of (output_dir, txt_output_file)
    """
    output_dir = Path(settings.BASE_DIR) / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_output_file = output_dir / OUTPUT_FILE_TEXT
    txt_output_file.write_text(text, encoding="utf-8")
    return output_dir, txt_output_file


def save_subjects(
    output_dir: Path, url: str, from_semester: int, to_semester: int, subjects: list[str]
) -> Path:
    """
    Save extracted subjects to JSON file.

    Args:
        output_dir: Directory to save file to
        url: Source URL
        from_semester: Starting semester
        to_semester: Ending semester
        subjects: List of extracted subject names

    Returns:
        Path to JSON output file
    """
    json_output = {
        JSON_KEY_URL: url,
        "from_semester": from_semester,
        "to_semester": to_semester,
        JSON_KEY_STUDY_SUBJECTS: subjects,
    }
    json_output_file = output_dir / OUTPUT_FILE_JSON
    json_output_file.write_text(
        json.dumps(json_output, ensure_ascii=False, indent=JSON_INDENT),
        encoding="utf-8",
    )
    return json_output_file
