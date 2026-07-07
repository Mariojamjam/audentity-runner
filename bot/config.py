from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
BOT_ENV_PATH = ROOT_DIR / ".env"
SERVER_DIR = ROOT_DIR / "server"
DEFAULT_COMPOSE_DIR = ROOT_DIR / "server"
DEFAULT_DOCKER_SERVICE_NAME = "minecraft"
DEFAULT_PLAYIT_SERVICE_NAME = "playit"
DEFAULT_DOCKER_CONTAINER_NAME = "minecraft-server"
DEFAULT_PLAYIT_CONTAINER_NAME = "playit-agent"


@dataclass(frozen=True)
class BotConfig:
    discord_token: str | None
    authorized_user_ids: list[int]
    playit_tunnel_address: str
    command_prefix: str
    docker_container_name: str
    docker_compose_dir: Path
    docker_service_name: str
    playit_service_name: str
    playit_container_name: str
    rcon_host: str
    rcon_port: int
    rcon_password: str
    rcon_retries: int
    rcon_retry_delay: float


def _parse_authorized_users(raw_value: str | None) -> list[int]:
    if not raw_value:
        return []

    normalized = (
        raw_value.strip("[]")
        .replace(" ", "")
        .replace('"', "")
        .replace("'", "")
    )
    return [int(item) for item in normalized.split(",") if item]


def load_config() -> BotConfig:
    load_dotenv(BOT_ENV_PATH)

    values = dotenv_values(BOT_ENV_PATH)

    return BotConfig(
        discord_token=values.get("DISCORD_TOKEN"),
        authorized_user_ids=_parse_authorized_users(values.get("AUTHORIZED_USERS")),
        playit_tunnel_address=values.get("PLAYIT_TUNNEL_ADDRESS", ""),
        command_prefix=values.get("COMMAND_PREFIX", "!R:"),
        docker_container_name=DEFAULT_DOCKER_CONTAINER_NAME,
        docker_compose_dir=DEFAULT_COMPOSE_DIR,
        docker_service_name=DEFAULT_DOCKER_SERVICE_NAME,
        playit_service_name=DEFAULT_PLAYIT_SERVICE_NAME,
        playit_container_name=DEFAULT_PLAYIT_CONTAINER_NAME,
        rcon_host=values.get("RCON_HOST", "127.0.0.1"),
        rcon_port=int(values.get("RCON_PORT", 25575)),
        rcon_password=values.get("RCON_PASSWORD", ""),
        rcon_retries=int(values.get("RCON_RETRIES", 3)),
        rcon_retry_delay=float(values.get("RCON_RETRY_DELAY", 2)),
    )
