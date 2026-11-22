"""
Subject extraction logic from Ollama responses.
Handles parsing, normalization, and fallback strategies.
"""
import json
from typing import Any

from .constants import (
    JSON_KEY_STUDY_SUBJECTS,
    LINE_STRIP_CHARS,
    SKIP_TOKENS,
)


def normalize_subject_names(raw_subjects: Any) -> list[str]:
    """
    Normalize and deduplicate subject names.

    - Removes empty strings and non-string items
    - Filters out JSON/markdown artifacts
    - Case-insensitive deduplication

    Args:
        raw_subjects: List of raw subject names from Ollama

    Returns:
        List of cleaned, deduplicated subject names
    """
    if not isinstance(raw_subjects, list):
        return []

    cleaned = []
    seen = set()

    for item in raw_subjects:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        compact = value.replace(" ", "")
        if value in SKIP_TOKENS:
            continue
        if compact.startswith('study_subjects":[') or compact.startswith("study_subjects:["):
            continue

        key = value.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

    return cleaned


def extract_subject_names_from_ollama_output(raw_content: str) -> list[str]:
    """
    Extract subject names from Ollama AI response.

    Attempts multiple parsing strategies:
    1. Direct JSON parse
    2. Find JSON boundaries and parse substring
    3. Fallback to line-by-line parsing

    Args:
        raw_content: Raw response text from Ollama API

    Returns:
        List of extracted and normalized subject names
    """
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

    if isinstance(parsed, dict) and isinstance(parsed.get(JSON_KEY_STUDY_SUBJECTS), list):
        return normalize_subject_names(parsed[JSON_KEY_STUDY_SUBJECTS])

    fallback = [
        line.strip(LINE_STRIP_CHARS)
        for line in raw_content.splitlines()
        if line.strip(LINE_STRIP_CHARS)
    ]
    return normalize_subject_names(fallback)
