"""Tests for the redact_key helper."""

from custom_components.bark.entity import redact_key


def test_redact_key_normal():
    assert redact_key("abcdefghijklmnop") == "abcd***mnop"


def test_redact_key_short():
    assert redact_key("abc") == "<redacted>"


def test_redact_key_none():
    assert redact_key(None) == "<none>"


def test_redact_key_boundary_eight_chars():
    # exactly 8 chars → too short to safely redact (would reveal nothing useful)
    assert redact_key("12345678") == "<redacted>"
