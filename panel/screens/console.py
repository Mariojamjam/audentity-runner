from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.widgets import Input, Label, Log


COMMON_COMMANDS = [
    "say",
    "give",
    "tp",
    "gamemode",
    "weather",
    "time",
    "whitelist add",
    "whitelist remove",
    "op",
    "deop",
    "kick",
    "ban",
    "pardon",
]


class ConsoleScreen(Vertical):
    DEFAULT_CLASSES = "screen-view"

    def __init__(self, panel_services, *, id: str | None = None):
        super().__init__(id=id)
        self.services = panel_services
        self.history: list[str] = []
        self.history_index = 0

    def compose(self) -> ComposeResult:
        yield Label("RCON Console", classes="screen-title")
        yield Log(id="console-output", highlight=True)
        yield Input(placeholder="Type any Minecraft command and press Enter", id="console-input")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        if not command:
            return

        self.history.append(command)
        self.history_index = len(self.history)
        event.input.value = ""

        output = self.query_one("#console-output", Log)
        output.write_line(f"> {command}")
        response = await asyncio.to_thread(self.services.send_command, command)
        output.write_line(response or "(no response)")

    async def on_key(self, event: Key) -> None:
        if self.screen.focused is not self.query_one("#console-input", Input):
            return

        input_widget = self.query_one("#console-input", Input)
        if event.key == "up":
            if self.history and self.history_index > 0:
                self.history_index -= 1
                input_widget.value = self.history[self.history_index]
                input_widget.cursor_position = len(input_widget.value)
                event.stop()
        elif event.key == "down":
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                input_widget.value = self.history[self.history_index]
            else:
                self.history_index = len(self.history)
                input_widget.value = ""
            input_widget.cursor_position = len(input_widget.value)
            event.stop()
        elif event.key == "tab":
            prefix = input_widget.value.strip()
            if not prefix:
                return
            match = next((cmd for cmd in COMMON_COMMANDS if cmd.startswith(prefix)), None)
            if match:
                input_widget.value = match
                input_widget.cursor_position = len(match)
                event.stop()
