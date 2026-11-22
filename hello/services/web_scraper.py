"""
Web scraping functionality for fetching and processing webpage content.
Handles HTTP requests with retry logic and HTML text extraction.
"""
import time

import requests
from bs4 import BeautifulSoup

from .constants import (
    MAX_RETRIES,
    MAX_TEXT_LENGTH,
    REQUEST_TIMEOUT,
    RETRY_DELAY,
    TEXT_SEPARATOR,
)
from .request_validator import ScrapeTextError
from rest_framework import status


def fetch_webpage_text(url: str) -> str:
    """
    Fetch webpage content and extract clean text.

    Implements retry logic for transient failures.
    Removes script, style, and noscript tags before text extraction.
    Limits output to MAX_TEXT_LENGTH characters.

    Args:
        url: URL to fetch

    Returns:
        Extracted text from webpage

    Raises:
        ScrapeTextError: On HTTP errors or after MAX_RETRIES attempts
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            break
        except requests.HTTPError as exc:
            raise ScrapeTextError(
                f"HTTP error: {exc.response.status_code}",
                status.HTTP_400_BAD_REQUEST,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == MAX_RETRIES - 1:
                raise ScrapeTextError(
                    f"Failed after {MAX_RETRIES} attempts: {exc}",
                    status.HTTP_400_BAD_REQUEST,
                )
            time.sleep(RETRY_DELAY)
        except requests.RequestException as exc:
            raise ScrapeTextError(
                f"Request failed: {exc}",
                status.HTTP_400_BAD_REQUEST,
            )

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.extract()
    return soup.get_text(separator=TEXT_SEPARATOR, strip=True)[:MAX_TEXT_LENGTH]
