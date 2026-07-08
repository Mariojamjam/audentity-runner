from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label, ListItem, ListView

from panel.player_manager import PlayerEntry


class PlayerRow(ListItem):
    def __init__(self, player: PlayerEntry):
        super().__init__(classes="player-row")
        self.player = player

    def compose(self) -> ComposeResult:
        operator_text = " [op]" if self.player.is_operator else ""
        yield Label(
            f"{_icon_for(self.player)} {self.player.name}{operator_text}",
            classes="player-row-label",
        )


class PlayerList(ListView):
    async def set_players(self, players: list[PlayerEntry], selected_name: str | None = None) -> None:
        await self.clear()
        if players:
            await self.extend(PlayerRow(player) for player in players)
            if selected_name is not None:
                selected_index = next(
                    (index for index, player in enumerate(players) if player.name == selected_name),
                    0,
                )
            else:
                selected_index = 0
            self.index = selected_index
        else:
            self.index = None


def _icon_for(player: PlayerEntry) -> str:
    if player.status_icon == "green_circle":
        return "+"
    if player.status_icon == "star":
        return "*"
    return "o"
