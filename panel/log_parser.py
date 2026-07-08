from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


LOG_PATTERNS = {
    "join": re.compile(r"(?P<player>[\w.\-]+) joined the game", re.IGNORECASE),
    "leave": re.compile(r"(?P<player>[\w.\-]+) left the game", re.IGNORECASE),
    "chat": re.compile(r"(?:\[Not Secure\]\s)?<(?P<player>[^>]+)>\s(?P<message>.+)$"),
    "login": re.compile(r"(?P<player>[\w.\-]+)\[.+\] logged in with entity id", re.IGNORECASE),
    "death": re.compile(
        r"(?P<player>[\w.\-]+)\s(?:was|fell|drowned|blew up|walked into|hit the ground|was slain by|was shot by|was killed by)",
        re.IGNORECASE,
    ),
    "warning": re.compile(r"\b(?:warn|warning|can't keep up)\b", re.IGNORECASE),
    "error": re.compile(r"\b(?:error|exception|failed|fatal)\b", re.IGNORECASE),
}


@dataclass(slots=True)
class ParsedLogLine:
    raw: str
    timestamp: str
    category: str
    player: str | None = None
    message: str | None = None


def parse_log_line(raw_line: str) -> ParsedLogLine:
    line = raw_line.rstrip("\n")
    timestamp = _extract_timestamp(line)
    message_body = _extract_message_body(line)

    for category, pattern in LOG_PATTERNS.items():
        match = pattern.search(message_body)
        if match:
            groups = match.groupdict()
            return ParsedLogLine(
                raw=message_body,
                timestamp=timestamp,
                category=category,
                player=groups.get("player"),
                message=groups.get("message"),
            )

    return ParsedLogLine(raw=message_body, timestamp=timestamp, category="other")


def _extract_timestamp(line: str) -> str:
    bracket_timestamp = re.search(r"\[(\d{1,2}:\d{2}:\d{2})\]", line)
    if bracket_timestamp:
        return bracket_timestamp.group(1)

    return datetime.now().strftime("%H:%M:%S")


def _extract_message_body(line: str) -> str:
    match = re.search(r"\]:\s(?P<body>.+)$", line)
    if match:
        return match.group("body")
    return line
