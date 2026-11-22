"""
Request validation for scrape operations.
Validates URLs, semesters, and required fields.
"""
from typing import Any

from rest_framework import status

from .constants import (
    JSON_KEY_FROM_SEMESTER,
    JSON_KEY_TO_SEMESTER,
    JSON_KEY_URL,
    MAX_SEMESTER,
    MIN_SEMESTER,
    VALID_URL_SCHEMES,
)


class ScrapeTextError(Exception):
    """Custom exception for scrape text operations with HTTP status codes."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class RequestValidator:
    """Validates scrape request payloads."""

    @staticmethod
    def validate_field_exists(payload: dict, field: str, friendly_name: str) -> None:
        """Check required field exists."""
        if field not in payload:
            raise ScrapeTextError(
                f"Field '{friendly_name}' is required.",
                status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def validate_integer(value: Any, field_name: str) -> int:
        """Convert and validate integer field."""
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ScrapeTextError(
                f"{field_name} must be a number.",
                status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def validate_semester_range(from_sem: int, to_sem: int) -> None:
        """Validate semester numbers."""
        if from_sem < MIN_SEMESTER or to_sem < MIN_SEMESTER:
            raise ScrapeTextError(
                f"fromSemester and toSemester must be at least {MIN_SEMESTER}.",
                status.HTTP_400_BAD_REQUEST,
            )
        if from_sem > MAX_SEMESTER or to_sem > MAX_SEMESTER:
            raise ScrapeTextError(
                f"fromSemester and toSemester must be at most {MAX_SEMESTER}.",
                status.HTTP_400_BAD_REQUEST,
            )
        if from_sem > to_sem:
            raise ScrapeTextError(
                "fromSemester cannot be greater than toSemester.",
                status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format."""
        url = (url or "").strip()
        if not url:
            raise ScrapeTextError(
                "Field 'url' is required.",
                status.HTTP_400_BAD_REQUEST,
            )
        if not any(url.startswith(scheme) for scheme in VALID_URL_SCHEMES):
            raise ScrapeTextError(
                "URL must start with http:// or https://.",
                status.HTTP_400_BAD_REQUEST,
            )
        return url

    @classmethod
    def validate_scrape_request(cls, payload: dict) -> tuple[str, int, int]:
        """Main validation entry point."""
        # Check for both required fields first (before raising error)
        missing_fields = []
        if JSON_KEY_FROM_SEMESTER not in payload:
            missing_fields.append("fromSemester")
        if JSON_KEY_TO_SEMESTER not in payload:
            missing_fields.append("toSemester")
        
        if missing_fields:
            if len(missing_fields) == 2:
                raise ScrapeTextError(
                    "Fields 'fromSemester' and 'toSemester' are required.",
                    status.HTTP_400_BAD_REQUEST,
                )
            else:
                raise ScrapeTextError(
                    f"Field '{missing_fields[0]}' is required.",
                    status.HTTP_400_BAD_REQUEST,
                )

        from_sem = cls.validate_integer(
            payload.get(JSON_KEY_FROM_SEMESTER), "fromSemester"
        )
        to_sem = cls.validate_integer(payload.get(JSON_KEY_TO_SEMESTER), "toSemester")

        cls.validate_semester_range(from_sem, to_sem)

        url = cls.validate_url(payload.get(JSON_KEY_URL))

        return url, from_sem, to_sem
