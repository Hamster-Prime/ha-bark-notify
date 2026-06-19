"""Bark API client and data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BarkPayload:
    """Bark push payload (internal snake_case names)."""

    title: str | None = None
    subtitle: str | None = None
    body: str | None = None
    markdown: str | None = None
    level: str | None = None
    volume: int | None = None
    badge: int | None = None
    call: bool | None = None
    auto_copy: bool | None = None
    copy: str | None = None
    sound: str | None = None
    icon: str | None = None
    image: str | None = None
    group: str | None = None
    is_archive: bool | None = None
    ttl: int | None = None
    url: str | None = None
    action: str | None = None
    id: str | None = None
    delete: bool | None = None

    def to_bark_dict(self) -> dict[str, Any]:
        """Convert to Bark wire-format dict (camelCase, bools as '1')."""
        data: dict[str, Any] = {}
        if self.markdown:
            data["markdown"] = self.markdown
        elif self.body is not None:
            data["body"] = self.body
        if self.title is not None:
            data["title"] = self.title
        if self.subtitle is not None:
            data["subtitle"] = self.subtitle
        if self.level is not None:
            data["level"] = self.level
            if self.level == "critical" and self.volume is not None:
                data["volume"] = self.volume
        if self.badge is not None:
            data["badge"] = self.badge
        if self.call:
            data["call"] = "1"
        if self.auto_copy:
            data["autoCopy"] = "1"
        if self.copy is not None:
            data["copy"] = self.copy
        if self.sound is not None:
            data["sound"] = self.sound
        if self.icon is not None:
            data["icon"] = self.icon
        if self.image is not None:
            data["image"] = self.image
        if self.group is not None:
            data["group"] = self.group
        if self.is_archive:
            data["isArchive"] = "1"
        if self.ttl is not None:
            data["ttl"] = self.ttl
        if self.url is not None:
            data["url"] = self.url
        if self.action is not None:
            data["action"] = self.action
        if self.id is not None:
            data["id"] = self.id
        if self.delete:
            data["delete"] = "1"
        return data
