from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListView, Static

from panel.player_manager import PlayerEntry
from panel.widgets.player_list import PlayerList


class PlayersScreen(Vertical):
    DEFAULT_CLASSES = "screen-view"

    def __init__(self, panel_services, *, id: str | None = None):
        super().__init__(id=id)
        self.services = panel_services
        self.players: list[PlayerEntry] = []
        self.selected_player: PlayerEntry | None = None

    def compose(self) -> ComposeResult:
        yield Label("Players", classes="screen-title")
        with Horizontal(classes="player-actions-row"):
            yield Button("Refresh", id="players-refresh")
            yield Button("Kick", id="players-kick", variant="warning")
            yield Button("Ban", id="players-ban", variant="error")
            yield Button("Message", id="players-message")
            yield Button("Op/Deop", id="players-op")
            yield Button("Whitelist +", id="players-whitelist-add")
            yield Button("Whitelist -", id="players-whitelist-remove")
        with Horizontal(id="players-layout"):
            with Vertical(classes="panel-box"):
                yield Static("Online players", classes="section-title")
                yield PlayerList(id="players-list")
            with Vertical(classes="panel-box"):
                yield Static("Player details", classes="section-title")
                yield Static("Select a player to inspect details.", id="players-details")
                yield Input(placeholder="Message or reason", id="players-input")

    async def refresh_players(self) -> None:
        await self.app.refresh_players(force=True)

    async def apply_players(self, players: list[PlayerEntry]) -> None:
        selected_name = self.selected_player.name if self.selected_player is not None else None
        previous_names = [player.name for player in self.players]
        current_names = [player.name for player in players]
        self.players = players

        if not players:
            player_list = self.query_one("#players-list", PlayerList)
            await player_list.set_players(players)
            self.selected_player = None
            self.query_one("#players-details", Static).update("No players online.")
            return

        if selected_name is not None:
            self.selected_player = next((player for player in players if player.name == selected_name), players[0])
        else:
            self.selected_player = players[0]

        if previous_names != current_names:
            player_list = self.query_one("#players-list", PlayerList)
            await player_list.set_players(players, self.selected_player.name)

        self.query_one("#players-details", Static).update(
            f"Player: {self.selected_player.name}\nSelect Refresh to reload detailed data."
        )

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.index
        if index is None:
            return
        if 0 <= index < len(self.players):
            self.selected_player = self.players[index]
            await self._refresh_details()

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        index = event.list_view.index
        if index is None:
            return
        if 0 <= index < len(self.players):
            self.selected_player = self.players[index]
            await self._refresh_details()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "players-refresh":
            await self.refresh_players()
            return

        if not self.selected_player:
            self.services.notify("No player is selected.")
            return

        player = self.selected_player.name
        input_widget = self.query_one("#players-input", Input)
        payload = input_widget.value.strip()

        if event.button.id == "players-kick":
            response = await asyncio.to_thread(self.services.player_action, "kick", player, payload)
        elif event.button.id == "players-ban":
            response = await asyncio.to_thread(self.services.player_action, "ban", player, payload)
        elif event.button.id == "players-message":
            if not payload:
                self.services.notify("Type a private message first.")
                return
            response = await asyncio.to_thread(self.services.player_action, "message", player, payload)
        elif event.button.id == "players-op":
            response = await asyncio.to_thread(self.services.toggle_op, player)
        elif event.button.id == "players-whitelist-add":
            response = await asyncio.to_thread(self.services.player_action, "whitelist_add", player, payload)
        elif event.button.id == "players-whitelist-remove":
            response = await asyncio.to_thread(self.services.player_action, "whitelist_remove", player, payload)
        else:
            return

        self.services.notify(response or "Action sent.")
        await self.app.refresh_players(force=True)

    async def _refresh_details(self) -> None:
        if not self.selected_player:
            return

        details = await asyncio.to_thread(self.services.player_details, self.selected_player.name)
        self.query_one("#players-details", Static).update(
            f"Player: {self.selected_player.name}\n{details}"
        )
