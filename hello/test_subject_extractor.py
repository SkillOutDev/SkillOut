import pytest

from hello.services.subject_extractor import (
    extract_subject_names_from_ollama_output,
    normalize_subject_names,
)


def test_normalize_subject_names_filters_artifacts_and_casefolds_duplicates():
    raw = [
        "  Mathematics  ",
        "mathematics",
        "Straße",
        "STRASSE",
        "",
        None,
        123,
        "{",
        'study_subjects": [',
        "Physics",
    ]

    assert normalize_subject_names(raw) == ["Mathematics", "Straße", "Physics"]


@pytest.mark.parametrize("raw", [None, "Math", {"name": "Math"}, ("Math",)])
def test_normalize_subject_names_requires_a_list(raw):
    assert normalize_subject_names(raw) == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"study_subjects": ["Math", " math ", "Physics"]}', ["Math", "Physics"]),
        ('Here are the subjects:\n{"study_subjects": ["Biology"]}\nDone.', ["Biology"]),
        (" - Math\n • Physics\n - math\n", ["Math", "Physics"]),
        ("", []),
        ("{bad json}\n- Math", ["{bad json}", "Math"]),
    ],
)
def test_extract_subjects_from_json_embedded_json_and_lines(raw, expected):
    assert extract_subject_names_from_ollama_output(raw) == expected


def test_extract_subjects_falls_back_when_json_has_wrong_shape():
    assert extract_subject_names_from_ollama_output('{"other": ["Math"]}') == [
        '{"other": ["Math"]}'
    ]
