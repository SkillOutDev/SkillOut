"""
AI-powered subject extraction using Ollama.
Builds extraction prompts and communicates with Ollama API.
"""

from rest_framework import status

from .constants import (
    MARKDOWN_CODE_FENCE,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_P,
)
from .request_validator import ScrapeTextError
from .subject_extractor import extract_subject_names_from_ollama_output


def build_extraction_prompt(text: str, from_semester: int, to_semester: int) -> str:
    """
    Build AI prompt for subject extraction.

    Args:
        text: Webpage text to analyze
        from_semester: Starting semester number
        to_semester: Ending semester number

    Returns:
        Formatted prompt for Ollama
    """
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


def extract_subjects(text: str, from_semester: int, to_semester: int) -> list[str]:
    """
    Extract study subjects from text using Ollama AI.

    Args:
        text: Webpage text to analyze
        from_semester: Starting semester number
        to_semester: Ending semester number

    Returns:
        List of extracted subject names

    Raises:
        ScrapeTextError: If Ollama is not installed or request fails
    """
    try:
        import ollama
    except ImportError as exc:
        raise ScrapeTextError(
            "Ollama Python package is not installed. Install it with: pip install ollama",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    prompt = build_extraction_prompt(text, from_semester, to_semester)
    try:
        ollama_response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": OLLAMA_TEMPERATURE, "top_p": OLLAMA_TOP_P},
        )
    except Exception as exc:
        raise ScrapeTextError(
            f"Ollama request failed: {exc}",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    raw_content = ollama_response.get("message", {}).get("content", "").strip()
    if raw_content.startswith(MARKDOWN_CODE_FENCE):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

    return extract_subject_names_from_ollama_output(raw_content)
