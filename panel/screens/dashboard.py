from __future__ import annotations

import asyncio
import shutil
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, Label, Static

from panel.widgets.status_card import StatusCard


class DashboardScreen(Vertical):
    DEFAULT_CLASSES = "screen-view"

    def __init__(self, panel_services, *, id: str | None = None):
        super().__init__(id=id)
        self.services = panel_services

    def compose(self) -> ComposeResult:
        yield Label("Overview", classes="screen-title")
        with Grid(id="dashboard-grid"):
            yield StatusCard("Status", "Unknown", id="dashboard-status")
            yield StatusCard("Bot", "Unknown", id="dashboard-bot")
            yield StatusCard("Players", "No data yet", id="dashboard-players")
            yield StatusCard("Address", "Unavailable", id="dashboard-address")
        yield Label("Quick Actions", classes="section-title")
        with Horizontal(classes="action-row"):
            yield Button("Start", id="dashboard-start", variant="success")
            yield Button("Stop", id="dashboard-stop", variant="warning")
            yield Button("Restart", id="dashboard-restart", variant="primary")
            yield Button("Backup", id="dashboard-backup")
            yield Button("Start Bot", id="dashboard-toggle-bot", classes="bot-action-button")
        yield Static("Use S/T/R in the app for fast stack actions.", classes="hint")

    def apply_state(self, state) -> None:
        status_card = self.query_one("#dashboard-status", StatusCard)
        bot_card = self.query_one("#dashboard-bot", StatusCard)
        players_card = self.query_one("#dashboard-players", StatusCard)
        address_card = self.query_one("#dashboard-address", StatusCard)
        bot_button = self.query_one("#dashboard-toggle-bot", Button)

        status_text = "Online" if state.running else "Offline"
        bot_text = "Online" if state.bot_running else "Offline"
        status_card.body = f"{status_text}\nUptime: {state.uptime}"
        bot_card.body = bot_text
        players_card.body = f"Players: {state.player_count}"
        address_card.body = state.address or "Unavailable"
        bot_button.label = "Stop Bot" if state.bot_running else "Start Bot"
        bot_button.set_class(state.bot_running, "bot-action-online")
        bot_button.set_class(not state.bot_running, "bot-action-offline")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dashboard-start":
            await self.app.action_start_stack()
        elif event.button.id == "dashboard-stop":
            await self.app.action_stop_stack()
        elif event.button.id == "dashboard-restart":
            await self.app.action_restart_stack()
        elif event.button.id == "dashboard-toggle-bot":
            await self.app.action_toggle_bot()
        elif event.button.id == "dashboard-backup":
            message = await self.run_backup()
            self.services.notify(message)

    async def run_backup(self) -> str:
        backup_root = self.services.root_dir / "server" / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_root / f"backup-{timestamp}"
        await asyncio.to_thread(self.services.safe_rcon, "save-all flush")
        await asyncio.to_thread(self.services.safe_rcon, "save-off")
        try:
            world_dir = self.services.root_dir / "server" / "data" / "world"
            if not world_dir.exists():
                return "Backup skipped: world folder not found."
            await asyncio.to_thread(
                shutil.make_archive,
                str(backup_path),
                "zip",
                world_dir.parent,
                world_dir.name,
            )
            return f"Backup created: {backup_path.name}.zip"
        finally:
            await asyncio.to_thread(self.services.safe_rcon, "save-on")
