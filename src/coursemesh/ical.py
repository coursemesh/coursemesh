from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from . import __version__
from .models import CalendarEvent, CalendarTimeZone, ContentLine


@dataclass(frozen=True)
class ParsedCalendar:
    events: tuple[CalendarEvent, ...]
    timezones: tuple[CalendarTimeZone, ...]


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


def parse_calendar(text: str) -> ParsedCalendar:
    lines = unfold_lines(text)
    events: list[CalendarEvent] = []
    timezones: list[CalendarTimeZone] = []
    index = 0

    while index < len(lines):
        upper = lines[index].upper()
        if upper == "BEGIN:VEVENT":
            component, index = _consume_component(lines, index, "VEVENT")
            events.append(_parse_event(component))
            continue
        if upper == "BEGIN:VTIMEZONE":
            component, index = _consume_component(lines, index, "VTIMEZONE")
            timezones.append(_parse_timezone(component))
            continue
        index += 1

    tzids = [timezone.tzid for timezone in timezones]
    if len(set(tzids)) != len(tzids):
        raise ValueError("iCalendar contains duplicate VTIMEZONE definitions for the same TZID")

    return ParsedCalendar(tuple(events), tuple(timezones))


def parse_events(text: str) -> list[CalendarEvent]:
    """Backward-compatible event-only parser used by callers and tests."""

    return list(parse_calendar(text).events)


def _consume_component(
    lines: list[str], start: int, component_name: str
) -> tuple[list[str], int]:
    stack = [component_name]
    component = [lines[start]]

    for index in range(start + 1, len(lines)):
        raw = lines[index]
        upper = raw.upper()
        if upper.startswith("BEGIN:"):
            stack.append(upper.split(":", 1)[1])
        elif upper.startswith("END:"):
            ending = upper.split(":", 1)[1]
            if not stack or ending != stack[-1]:
                expected = stack[-1] if stack else "nothing"
                raise ValueError(
                    f"Mismatched iCalendar component ending {ending!r}; expected {expected!r}"
                )
            stack.pop()

        component.append(raw)
        if not stack:
            return component, index + 1

    raise ValueError(f"Unclosed {component_name} component")


def _parse_event(component: list[str]) -> CalendarEvent:
    lines = [parse_content_line(raw) for raw in component[1:-1] if raw]
    uid = next((line.value for line in lines if line.name == "UID"), None)
    if not uid:
        raise ValueError("VEVENT is missing required UID")
    return CalendarEvent(uid=uid, lines=lines)


def _parse_timezone(component: list[str]) -> CalendarTimeZone:
    depth = 0
    tzids: list[str] = []

    for raw in component[1:-1]:
        if not raw:
            continue
        upper = raw.upper()
        if upper.startswith("BEGIN:"):
            depth += 1
            continue
        if upper.startswith("END:"):
            depth -= 1
            continue
        if depth == 0:
            line = parse_content_line(raw)
            if line.name == "TZID":
                tzids.append(line.value)

    if len(tzids) != 1 or not tzids[0]:
        raise ValueError("VTIMEZONE must contain exactly one non-empty TZID")
    return CalendarTimeZone(tzid=tzids[0], lines=tuple(line for line in component if line))


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


def render_calendar(
    events: Iterable[tuple[str, str, CalendarEvent]],
    timezones: Iterable[tuple[str, CalendarTimeZone]] = (),
) -> str:
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//CourseMesh//CourseMesh {__version__}//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:CourseMesh",
    ]
    for timezone in _merge_timezones(timezones):
        out.extend(timezone.lines)
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


def _merge_timezones(
    timezones: Iterable[tuple[str, CalendarTimeZone]],
) -> list[CalendarTimeZone]:
    by_tzid: dict[str, tuple[str, CalendarTimeZone]] = {}
    for source_id, timezone in timezones:
        previous = by_tzid.get(timezone.tzid)
        if previous is None:
            by_tzid[timezone.tzid] = (source_id, timezone)
            continue
        previous_source, previous_timezone = previous
        if previous_timezone.lines != timezone.lines:
            raise ValueError(
                "Conflicting VTIMEZONE definitions for "
                f"TZID {timezone.tzid!r} from sources "
                f"{previous_source!r} and {source_id!r}"
            )
    return [by_tzid[tzid][1] for tzid in sorted(by_tzid, key=str.casefold)]


def _escape_uid(value: str) -> str:
    return value.replace(" ", "-").replace("@", "-")


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
