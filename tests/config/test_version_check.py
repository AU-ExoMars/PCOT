"""
Tests for pcot.compatible_version_check(), which decides whether the running app is new
enough to load a document written by a given PCOT version, and for pcot.oldest_valid_version,
the floor version it's compared against (parsed from the second line of VERSION.txt).
"""
import pytest

import pcot


def test_oldest_valid_version_is_clean():
    """VERSION.txt's second line has a trailing '# ...' comment; oldest_valid_version must
    not include it, and must parse as three plain integers"""
    parts = pcot.oldest_valid_version.split(".")
    assert len(parts) == 3
    for p in parts:
        int(p)  # raises ValueError if any comment/whitespace leaked in


# all cases below are relative to a floor version of "10.10.10" - a double digit at every
# component, so cases can specifically exercise the old string-comparison bug where e.g.
# "9" > "10" lexicographically even though 9 < 10 numerically
version_check_tests = [
    # (doc version, expected result, description)
    ("10.10.10", True, "identical to floor"),
    ("10.10.10-beta", True, "identical to floor with suffix stripped"),
    ("10.10.9", False, "patch below double-digit floor (9 < 10)"),
    ("10.10.11", True, "patch above double-digit floor (11 > 10)"),
    ("10.9.20", False, "minor below double-digit floor (9 < 10)"),
    ("10.11.0", True, "minor above double-digit floor (11 > 10)"),
    ("9.20.20", False, "major below double-digit floor (9 < 10)"),
    ("11.0.0", True, "major above double-digit floor (11 > 10)"),
]


@pytest.mark.parametrize("version,expected,desc", version_check_tests, ids=[t[2] for t in version_check_tests])
def test_compatible_version_check(monkeypatch, version, expected, desc):
    """Check compatible_version_check compares version components numerically, not as strings,
    and correctly strips '-beta'-style suffixes from the document version"""
    monkeypatch.setattr(pcot, "oldest_valid_version", "10.10.10")
    assert pcot.compatible_version_check(version) == expected
