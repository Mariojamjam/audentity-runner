from __future__ import annotations

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static


class StatusCard(Vertical):
    DEFAULT_CLASSES = "status-card"

    title = reactive("Status")
    body = reactive("")

    def __init__(self, title: str, body: str = "", *, id: str | None = None):
        super().__init__(id=id)
        self.title = title
        self.body = body

    def compose(self):
        yield Static(self.title, classes="status-card-title")
        yield Static(self.body, classes="status-card-body")

    def watch_title(self, title: str) -> None:
        if self.children:
            self.query_one(".status-card-title", Static).update(title)

    def watch_body(self, body: str) -> None:
        if self.children:
            self.query_one(".status-card-body", Static).update(body)
