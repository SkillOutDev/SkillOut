"""
Services module for SkillOut application.
Provides web scraping and subject extraction functionality.
"""

from .request_validator import ScrapeTextError
from .scrape_text import process_scrape_text

__all__ = [
    "process_scrape_text",
    "ScrapeTextError",
]
