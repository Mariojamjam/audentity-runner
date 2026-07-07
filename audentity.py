from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"
COMPOSE_FILE = ROOT_DIR / "server" / "docker-compose.yml"
STATE_DIR = ROOT_DIR / ".audentity"
BOT_PID_FILE = STATE_DIR / "bot.pid"
BOT_LOG_FILE = STATE_DIR / "bot.log"


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


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def read_bot_pid() -> int | None:
    if not BOT_PID_FILE.exists():
        return None

    try:
        return int(BOT_PID_FILE.read_text(encoding="utf-8").strip())
    except (TypeError, ValueError):
        return None


def write_bot_pid(pid: int) -> None:
    BOT_PID_FILE.write_text(f"{pid}\n", encoding="utf-8")


def clear_bot_pid() -> None:
    if BOT_PID_FILE.exists():
        BOT_PID_FILE.unlink()


def is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "").strip()
        return output != "" and "No tasks are running" not in output

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def start_bot() -> None:
    ensure_state_dir()
    existing_pid = read_bot_pid()
    if existing_pid and is_process_running(existing_pid):
        print(f"Bot is already running with PID {existing_pid}.")
        print(f"Bot log: {BOT_LOG_FILE}")
        return

    clear_bot_pid()

    log_handle = BOT_LOG_FILE.open("a", encoding="utf-8")
    kwargs: dict = {
        "cwd": ROOT_DIR,
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": log_handle,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen([sys.executable, "runner.py"], **kwargs)
    write_bot_pid(process.pid)

    print(f"Bot started with PID {process.pid}.")
    print(f"Bot log: {BOT_LOG_FILE}")


def stop_bot() -> None:
    pid = read_bot_pid()
    if not pid:
        print("No tracked bot process was found.")
        return

    if not is_process_running(pid):
        clear_bot_pid()
        print("Tracked bot process is no longer running.")
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

        for _ in range(20):
            if not is_process_running(pid):
                break
            time.sleep(0.25)

        if is_process_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    clear_bot_pid()
    print(f"Bot process {pid} stopped.")


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
    start_bot()
    print("Audentity Runner is up.")


def all_down() -> None:
    stop_bot()
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
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(detail)
        return 1

    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
