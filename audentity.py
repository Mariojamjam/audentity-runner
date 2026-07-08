from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, NotFound


ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"
COMPOSE_FILE = ROOT_DIR / "docker-compose.yml"
BOT_SERVICE_NAME = "bot"
BOT_CONTAINER_NAME = "audentity-bot"


def compose_command(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        str(ENV_FILE),
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )


def _docker_client():
    try:
        return docker.from_env()
    except DockerException as exc:
        raise RuntimeError("Could not connect to Docker. Make sure Docker Desktop is running.") from exc


def bot_status() -> tuple[bool, str | None]:
    client = _docker_client()
    try:
        container = client.containers.get(BOT_CONTAINER_NAME)
    except NotFound:
        return (False, None)
    except APIError as exc:
        raise RuntimeError(f"Failed to inspect the bot container: {exc.explanation}") from exc

    try:
        container.reload()
    except APIError as exc:
        raise RuntimeError(f"Failed to refresh the bot container: {exc.explanation}") from exc

    status = container.status
    return (status == "running", status)


def start_bot_message() -> str:
    running, status = bot_status()
    if running:
        return "Bot container is already running."

    result = run_command(compose_command("up", "-d", BOT_SERVICE_NAME))
    detail = result.stdout.strip()
    if detail:
        return f"Bot container started.\n{detail}"
    return "Bot container started."


def start_bot() -> None:
    print(start_bot_message())


def stop_bot_message() -> str:
    running, status = bot_status()
    if not running and status is None:
        return "Bot container does not exist yet. Start it once with `all-up` or the dashboard."
    if not running:
        return f"Bot container is already stopped ({status})."

    result = run_command(compose_command("stop", BOT_SERVICE_NAME))
    detail = result.stdout.strip()
    if detail:
        return f"Bot container stopped.\n{detail}"
    return "Bot container stopped."


def stop_bot() -> None:
    print(stop_bot_message())


def stack_up() -> None:
    print("Starting Docker stack...")
    result = run_command(compose_command("up", "-d"))
    if result.stdout.strip():
        print(result.stdout.strip())
    print("Docker stack started.")


def stack_down() -> None:
    print("Stopping Docker stack...")
    result = run_command(compose_command("down"))
    if result.stdout.strip():
        print(result.stdout.strip())
    print("Docker stack stopped.")


def all_up() -> None:
    stack_up()
    print("Audentity Runner is up.")


def all_down() -> None:
    stack_down()
    print("Audentity Runner is down.")


def print_usage() -> None:
    print("Usage:")
    print("  python audentity all-up")
    print("  python audentity all-down")
    print("  python audentity.py all-up")
    print("  python audentity.py all-down")


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print_usage()
        return 1

    command = argv[0]

    try:
        if command == "all-up":
            all_up()
            return 0
        if command == "all-down":
            all_down()
            return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        else:
            detail = str(exc)
        print(detail)
        return 1

    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
