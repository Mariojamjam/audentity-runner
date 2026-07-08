from __future__ import annotations

from dataclasses import dataclass

from bot.rcon_client import RconClient


@dataclass(slots=True)
class PlayerEntry:
    name: str
    online: bool = True
    is_operator: bool = False
    status_icon: str = "green_circle"
    details: str = "No extra details available."


class PlayerManager:
    def __init__(self, rcon_client: RconClient):
        self.rcon_client = rcon_client

    def list_players(self) -> list[PlayerEntry]:
        response = self.rcon_client.command("list")
        names = _extract_players_from_list_response(response)
        return [PlayerEntry(name=name) for name in names]

    def kick(self, player: str, reason: str = "Removed by admin panel") -> str:
        return self.rcon_client.command(f"kick {player} {reason}")

    def ban(self, player: str, reason: str = "Banned by admin panel") -> str:
        return self.rcon_client.command(f"ban {player} {reason}")

    def message(self, player: str, message: str) -> str:
        return self.rcon_client.command(f"tell {player} {message}")

    def op(self, player: str) -> str:
        return self.rcon_client.command(f"op {player}")

    def deop(self, player: str) -> str:
        return self.rcon_client.command(f"deop {player}")

    def whitelist_list(self) -> str:
        return self.rcon_client.command("whitelist list")

    def whitelist_add(self, player: str) -> str:
        return self.rcon_client.command(f"whitelist add {player}")

    def whitelist_remove(self, player: str) -> str:
        return self.rcon_client.command(f"whitelist remove {player}")

    def player_details(self, player: str) -> str:
        try:
            return self.rcon_client.command(f"data get entity {player} Pos")
        except Exception:  # noqa: BLE001
            return "No extra details available."


def _extract_players_from_list_response(response: str) -> list[str]:
    if ":" not in response:
        return []

    _, _, player_section = response.partition(":")
    names = [item.strip() for item in player_section.split(",") if item.strip()]
    return names
