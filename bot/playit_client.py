from __future__ import annotations

import json
import subprocess


class PlayitClient:
    def __init__(self, container_name: str, fallback_address: str = ""):
        self.container_name = container_name
        self.fallback_address = fallback_address

    def get_tunnel_address(self) -> str | None:
        for command in self._candidate_commands():
            output = self._run_command(command)
            address = self._extract_address(output)
            if address:
                return address

        return self.fallback_address or None

    def _candidate_commands(self) -> list[list[str]]:
        return [
            ["docker", "exec", self.container_name, "playit-cli", "tunnels", "list", "--json"],
            ["docker", "exec", self.container_name, "playit-cli", "tunnel", "list", "--json"],
            ["docker", "exec", self.container_name, "playit", "tunnels", "list", "--json"],
            ["docker", "exec", self.container_name, "playit", "tunnel", "list", "--json"],
        ]

    @staticmethod
    def _run_command(command: list[str]) -> str | None:
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

        stdout = result.stdout.strip()
        return stdout or None

    def _extract_address(self, output: str | None) -> str | None:
        if not output:
            return None

        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return self._extract_address_from_text(output)

        return self._find_address(payload)

    def _find_address(self, payload) -> str | None:
        if isinstance(payload, dict):
            for key in ("address", "domain", "assigned_domain", "tunnel_address"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value

            for key in ("tunnels", "data", "items", "entries"):
                nested = payload.get(key)
                value = self._find_address(nested)
                if value:
                    return value

            for value in payload.values():
                found = self._find_address(value)
                if found:
                    return found

        if isinstance(payload, list):
            for item in payload:
                found = self._find_address(item)
                if found:
                    return found

        return None

    @staticmethod
    def _extract_address_from_text(output: str) -> str | None:
        for token in output.replace("\n", " ").split():
            cleaned = token.strip("`\",'[]()")
            if ".playit.gg" in cleaned or ".ply.gg" in cleaned:
                return cleaned
        return None
