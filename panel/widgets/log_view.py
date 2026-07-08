from __future__ import annotations

from textual.widgets import Log

from panel.log_parser import ParsedLogLine


class LogView(Log):
    def append_parsed(self, entry: ParsedLogLine) -> None:
        self.write_line(_render_log_entry(entry))


def _render_log_entry(entry: ParsedLogLine) -> str:
    if entry.category == "chat" and entry.player and entry.message:
        return f"{entry.timestamp} [CHAT] <{entry.player}> {entry.message}"
    if entry.category in {"join", "leave", "death", "login"} and entry.player:
        return f"{entry.timestamp} [{entry.category.upper()}] {entry.raw}"
    return f"{entry.timestamp} [{entry.category.upper()}] {entry.raw}"
