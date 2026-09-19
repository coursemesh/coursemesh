from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json

_VOLATILE_FIELDS = {"DTSTAMP", "CREATED", "LAST-MODIFIED"}


@dataclass(frozen=True)
class ContentLine:
    name: str
    params: str
    value: str

    def render(self) -> str:
        suffix = f";{self.params}" if self.params else ""
        return f"{self.name}{suffix}:{self.value}"


@dataclass
class CalendarEvent:
    uid: str
    lines: list[ContentLine] = field(default_factory=list)

    @property
    def summary(self) -> str:
        for line in self.lines:
            if line.name == "SUMMARY":
                return unescape_text(line.value)
        return "(untitled event)"

    @property
    def starts_at(self) -> str | None:
        for line in self.lines:
            if line.name == "DTSTART":
                return line.value
        return None

    @property
    def recurrence_id(self) -> ContentLine | None:
        for line in self.lines:
            if line.name == "RECURRENCE-ID":
                return line
        return None

    @property
    def instance_key(self) -> str:
        recurrence = self.recurrence_id
        return json.dumps(
            [self.uid, recurrence.render() if recurrence else None],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def fingerprint(self) -> str:
        stable = [
            line.render()
            for line in self.lines
            if line.name not in _VOLATILE_FIELDS and line.name != "UID"
        ]
        payload = "\n".join(stable).encode("utf-8")
        return sha256(payload).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            {
                "uid": self.uid,
                "lines": [line.__dict__ for line in self.lines],
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> "CalendarEvent":
        data = json.loads(raw)
        return cls(
            uid=data["uid"],
            lines=[ContentLine(**line) for line in data["lines"]],
        )


@dataclass(frozen=True)
class CalendarTimeZone:
    """An unfolded VTIMEZONE component preserved from an upstream calendar."""

    tzid: str
    lines: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(
            {"tzid": self.tzid, "lines": list(self.lines)},
            ensure_ascii=False,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> "CalendarTimeZone":
        data = json.loads(raw)
        return cls(tzid=data["tzid"], lines=tuple(data["lines"]))


def unescape_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )
