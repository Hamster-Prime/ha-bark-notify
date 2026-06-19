"""Tests for BarkPayload serialization."""

from custom_components.bark.bark_api import BarkPayload


def test_body_serialized():
    payload = BarkPayload(body="hello")
    assert payload.to_bark_dict() == {"body": "hello"}


def test_markdown_overrides_body():
    payload = BarkPayload(body="hello", markdown="# title")
    data = payload.to_bark_dict()
    assert data == {"markdown": "# title"}
    assert "body" not in data


def test_full_field_mapping_and_camelcase():
    payload = BarkPayload(
        title="t",
        subtitle="st",
        body="b",
        level="critical",
        volume=7,
        badge=3,
        call=True,
        auto_copy=True,
        copy="copied",
        sound="minuet",
        icon="https://example.com/i.png",
        image="https://example.com/img.png",
        group="g",
        is_archive=True,
        ttl=60,
        url="https://example.com",
        action="alert",
        id="abc",
        delete=True,
    )
    assert payload.to_bark_dict() == {
        "body": "b",
        "title": "t",
        "subtitle": "st",
        "level": "critical",
        "volume": 7,
        "badge": 3,
        "call": "1",
        "autoCopy": "1",
        "copy": "copied",
        "sound": "minuet",
        "icon": "https://example.com/i.png",
        "image": "https://example.com/img.png",
        "group": "g",
        "isArchive": "1",
        "ttl": 60,
        "url": "https://example.com",
        "action": "alert",
        "id": "abc",
        "delete": "1",
    }


def test_volume_only_with_critical_level():
    payload = BarkPayload(level="active", volume=7)
    data = payload.to_bark_dict()
    assert data == {"level": "active"}
    assert "volume" not in data


def test_bool_false_omitted():
    payload = BarkPayload(body="x", call=False, delete=False, is_archive=False, auto_copy=False)
    assert payload.to_bark_dict() == {"body": "x"}


def test_none_fields_omitted():
    payload = BarkPayload()
    assert payload.to_bark_dict() == {}
