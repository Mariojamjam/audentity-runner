from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from panel.log_parser import ParsedLogLine
from panel.widgets.log_view import LogView


LOG_CATEGORIES = ["all", "chat", "join", "leave", "warning", "error", "death"]


class LogsScreen(Vertical):
    DEFAULT_CLASSES = "screen-view"

    def __init__(self, panel_services, *, id: str | None = None):
        super().__init__(id=id)
        self.services = panel_services
        self.entries: list[ParsedLogLine] = []
        self.active_category = "all"
        self._full_render_needed = True

    def compose(self) -> ComposeResult:
        yield Label("Live Logs", classes="screen-title")
        with Horizontal(classes="filter-row"):
            for category in LOG_CATEGORIES:
                variant = "primary" if category == "all" else "default"
                yield Button(category.title(), id=f"log-filter-{category}", variant=variant)
        yield LogView(id="logs-output", highlight=True)

    def add_entries(self, entries: list[ParsedLogLine], *, render: bool) -> None:
        self.entries.extend(entries)
        if len(self.entries) > 1000:
            self.entries = self.entries[-1000:]

        if not render:
            return

        if self._full_render_needed:
            self._full_render_needed = False
            self._refresh_output()
            return

        if self.active_category == "all":
            output = self.query_one("#logs-output", LogView)
            for entry in entries:
                output.append_parsed(entry)
            return

        self._refresh_output()

    def render_current(self) -> None:
        self.active_category = "all"
        self._full_render_needed = True
        self._sync_filter_buttons()
        self._refresh_output()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id.startswith("log-filter-"):
            self.active_category = event.button.id.removeprefix("log-filter-")
            self._sync_filter_buttons()
            self._refresh_output()

    def _refresh_output(self) -> None:
        output = self.query_one("#logs-output", LogView)
        output.clear()

        for entry in self.entries:
            if self.active_category != "all" and entry.category != self.active_category:
                continue
            output.append_parsed(entry)

    def _sync_filter_buttons(self) -> None:
        for category in LOG_CATEGORIES:
            button = self.query_one(f"#log-filter-{category}", Button)
            button.variant = "primary" if category == self.active_category else "default"
