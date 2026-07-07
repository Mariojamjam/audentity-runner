from __future__ import annotations

import time

from mcrcon import MCRcon


class RconError(RuntimeError):
    """Raised when RCON cannot complete an operation."""


class RconClient:
    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.retries = retries
        self.retry_delay = retry_delay

    def command(self, command: str) -> str:
        if not self.password:
            raise RconError("RCON_PASSWORD is not configured.")

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                with MCRcon(self.host, self.password, port=self.port) as rcon:
                    return rcon.command(command)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.retry_delay)

        raise RconError(f"Failed to execute RCON command: {last_error}") from last_error

    def graceful_stop(self) -> str:
        return self.command("stop")
