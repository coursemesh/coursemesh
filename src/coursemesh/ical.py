from __future__ import annotations

from collections.abc import Iterable

from . import __version__
from .models import CalendarEvent, ContentLine


def unfold_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded: list[str] = []
    for raw in normalized.split("\n"):
        if raw.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw)
    return unfolded


def parse_content_line(raw: str) -> ContentLine:
    separator = _value_separator(raw)
    if separator is None:
        raise ValueError(f"Invalid iCalendar content line: {raw!r}")
    left, value = raw[:separator], raw[separator + 1 :]
    if ";" in left:
        name, params = left.split(";", 1)
    else:
        name, params = left, ""
    if not name:
        raise ValueError(f"Invalid iCalendar content line: {raw!r}")
    return ContentLine(name=name.upper(), params=params, value=value)


def _value_separator(raw: str) -> int | None:
    in_quotes = False
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quotes = not in_quotes
            continue
        if char == ":" and not in_quotes:
            return index
    return None


def parse_events(text: str) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    current: list[ContentLine] | None = None
    nested_depth = 0

    for raw in unfold_lines(text):
        upper = raw.upper()
        if upper == "BEGIN:VEVENT":
            if current is not None:
                raise ValueError("Nested VEVENT is not valid")
            current = []
            nested_depth = 0
            continue
        if current is None:
            continue
        if upper.startswith("BEGIN:"):
            nested_depth += 1
            current.append(parse_content_line(raw))
            continue
        if upper.startswith("END:") and upper != "END:VEVENT":
            nested_depth = max(0, nested_depth - 1)
            current.append(parse_content_line(raw))
            continue
        if upper == "END:VEVENT" and nested_depth == 0:
            uid = next((line.value for line in current if line.name == "UID"), None)
            if not uid:
                raise ValueError("VEVENT is missing required UID")
            events.append(CalendarEvent(uid=uid, lines=current))
            current = None
            continue
        if raw:
            current.append(parse_content_line(raw))

    if current is not None:
        raise ValueError("Unclosed VEVENT")
    return events


def fold_line(line: str, limit: int = 75) -> list[str]:
    # RFC 5545 counts octets. This implementation folds on UTF-8 boundaries.
    chunks: list[str] = []
    remaining = line
    prefix = ""
    while len((prefix + remaining).encode("utf-8")) > limit:
        budget = limit - len(prefix.encode("utf-8"))
        cut = 0
        used = 0
        for idx, ch in enumerate(remaining):
            size = len(ch.encode("utf-8"))
            if used + size > budget:
                break
            used += size
            cut = idx + 1
        if cut == 0:
            cut = 1
        chunks.append(prefix + remaining[:cut])
        remaining = remaining[cut:]
        prefix = " "
    chunks.append(prefix + remaining)
    return chunks


def render_calendar(events: Iterable[tuple[str, str, CalendarEvent]]) -> str:
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//CourseMesh//CourseMesh {__version__}//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:CourseMesh",
    ]
    for source_id, source_name, event in events:
        out.append("BEGIN:VEVENT")
        out.append(f"UID:{_escape_uid(source_id)}.{event.uid}")
        out.append(f"X-COURSEMESH-SOURCE:{_escape_text(source_id)}")
        out.append(f"X-COURSEMESH-SOURCE-NAME:{_escape_text(source_name)}")
        for line in event.lines:
            if line.name == "UID":
                continue
            out.append(line.render())
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")

    folded: list[str] = []
    for line in out:
        folded.extend(fold_line(line))
    return "\r\n".join(folded) + "\r\n"


def _escape_uid(value: str) -> str:
    return value.replace(" ", "-").replace("@", "-")


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
