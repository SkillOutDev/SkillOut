"""
Configuration constants for web scraping and subject extraction services.
Centralized location for magic numbers and strings that may need adjustment.
"""

# HTTP request configuration
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Text processing
MAX_TEXT_LENGTH = 60000  # maximum characters to extract from webpage
TEXT_SEPARATOR = " "

# Semester validation
MIN_SEMESTER = 1
MAX_SEMESTER = 8

# Ollama AI model configuration
OLLAMA_MODEL = "llama3"
OLLAMA_TEMPERATURE = 0
OLLAMA_TOP_P = 0.1

# JSON output formatting
JSON_INDENT = 2

# Skip tokens for subject normalization
SKIP_TOKENS = {
    "{",
    "}",
    "[",
    "]",
    '"study_subjects": [',
    'study_subjects": [',
    'study_subjects\\": [',
}

# JSON field names
JSON_KEY_URL = "url"
JSON_KEY_FROM_SEMESTER = "fromSemester"
JSON_KEY_TO_SEMESTER = "toSemester"
JSON_KEY_STUDY_SUBJECTS = "study_subjects"

# URL validation
VALID_URL_SCHEMES = ("http://", "https://")

# Output files
OUTPUT_DIR = "scraped_text"
OUTPUT_FILE_TEXT = "latest_scrape.txt"
OUTPUT_FILE_JSON = "latest_subjects.json"

# Markdown/formatting
MARKDOWN_CODE_FENCE = "```"
LINE_STRIP_CHARS = "-• \t"
