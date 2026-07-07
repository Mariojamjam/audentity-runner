from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from bot.playit_client import PlayitClient


ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
COMPOSE_FILE = ROOT_DIR / "server" / "docker-compose.yml"
PLAYIT_SERVICE = "playit"
PLAYIT_CONTAINER = "playit-agent"
PLAYIT_SETUP_WIZARD_URL = "https://playit.gg/account/setup/wizard/new-account/"
PLAYIT_LOGIN_URL = "https://playit.gg/login"
PLAYIT_AGENTS_URL = "https://playit.gg/account/agents"
PLAYIT_NEW_TUNNEL_URL = "https://playit.gg/account/setup/new-tunnel"


def compose_command(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        str(ENV_PATH),
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        check=check,
        capture_output=True,
        text=True,
    )


def print_step(title: str) -> None:
    print()
    print(f"== {title} ==")


def check_docker() -> None:
    print_step("Checking Docker")
    try:
        docker_version = run_command(["docker", "--version"])
        compose_version = run_command(["docker", "compose", "version"])
    except FileNotFoundError:
        raise SystemExit("Docker was not found in PATH. Install Docker and try again.")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise SystemExit(f"Docker is installed but not usable right now: {detail}")

    print(docker_version.stdout.strip())
    print(compose_version.stdout.strip())


def ensure_files_and_dirs() -> None:
    print_step("Preparing files")
    if not ENV_PATH.exists():
        raise SystemExit(
            "The .env file does not exist. Copy .env.example to .env before running this script."
        )

    print(f"Using env file: {ENV_PATH}")


def read_env_lines() -> list[str]:
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def get_env_value(key: str) -> str:
    for line in read_env_lines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        current_key, current_value = line.split("=", 1)
        if current_key.strip() == key:
            return current_value.strip()
    return ""


def set_env_value(key: str, value: str) -> None:
    lines = read_env_lines()
    updated = False
    new_lines: list[str] = []

    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            current_key, _ = line.split("=", 1)
            if current_key.strip() == key:
                new_lines.append(f"{key}={value}")
                updated = True
                continue
        new_lines.append(line)

    if not updated:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def ensure_secret_key() -> str:
    print_step("Checking Playit secret key")
    secret_key = get_env_value("PLAYIT_SECRET_KEY")
    if secret_key:
        print("PLAYIT_SECRET_KEY already exists in .env")
        return secret_key

    print("PLAYIT_SECRET_KEY is missing.")
    print("Create it in your Playit account, then paste it here.")
    print(f"Login: {PLAYIT_LOGIN_URL}")
    print(f"Setup wizard: {PLAYIT_SETUP_WIZARD_URL}")
    print(f"Agents page: {PLAYIT_AGENTS_URL}")
    print()
    print("When Playit shows docker run / docker compose examples, copy only the SECRET_KEY value.")
    secret_key = input("Paste PLAYIT_SECRET_KEY here: ").strip()
    if not secret_key:
        raise SystemExit("No PLAYIT_SECRET_KEY was provided.")

    set_env_value("PLAYIT_SECRET_KEY", secret_key)
    print("PLAYIT_SECRET_KEY saved to .env")
    return secret_key


def start_playit_service() -> None:
    print_step("Starting Playit service")
    try:
        result = run_command(compose_command("up", "-d", PLAYIT_SERVICE))
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise SystemExit(f"Could not start the Playit service: {detail}")

    if result.stdout.strip():
        print(result.stdout.strip())
    print("Playit service started.")


def show_recent_logs() -> None:
    print_step("Recent Playit logs")
    try:
        result = run_command(compose_command("logs", "--tail=40", PLAYIT_SERVICE), check=False)
    except FileNotFoundError:
        return

    output = (result.stdout or "") + (result.stderr or "")
    output = output.strip()
    if output:
        print(output)
    else:
        print("No logs available.")


def print_manual_tunnel_steps() -> None:
    print_step("Create the tunnel in Playit")
    print(f"New tunnel page: {PLAYIT_NEW_TUNNEL_URL}")
    print("Now create the Minecraft tunnel in the Playit dashboard:")
    print("1. Open the New Tunnel page in Playit.")
    print("2. Create a new tunnel.")
    print("3. Choose TCP as the tunnel type.")
    print("4. Select the Docker agent you created for this project.")
    print("5. Set the local port to 25565.")
    print("6. Save the tunnel.")
    print("7. Wait a few seconds for the tunnel to become active.")


def wait_for_user_confirmation() -> None:
    print()
    input("Press Enter after you finish creating the tunnel...")


def detect_tunnel_address() -> str | None:
    client = PlayitClient(container_name=PLAYIT_CONTAINER)
    for _ in range(5):
        address = client.get_tunnel_address()
        if address:
            return address
        time.sleep(2)
    return None


def print_final_status() -> None:
    print_step("Checking the public tunnel")
    address = detect_tunnel_address()
    if address:
        print(f"Tunnel detected: {address}")
        print("You can now start the full stack and run the Discord bot.")
        return

    print("No public tunnel address was detected yet.")
    print("If the tunnel was just created, wait a little and run this script again.")
    print("You can also inspect logs manually with:")
    print(f"  docker compose --env-file {ENV_PATH} -f {COMPOSE_FILE} logs -f {PLAYIT_SERVICE}")


def main() -> None:
    print("Audentity Runner - Playit setup wizard")
    check_docker()
    ensure_files_and_dirs()
    ensure_secret_key()
    start_playit_service()
    show_recent_logs()
    print_manual_tunnel_steps()
    wait_for_user_confirmation()
    print_final_status()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nSetup cancelled by user.")
