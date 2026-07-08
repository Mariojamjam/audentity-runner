from __future__ import annotations

import asyncio
from threading import Event
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Any

import docker
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from bot.config import load_config
from bot.docker_manager import DockerManager
from bot.playit_client import PlayitClient
from bot.rcon_client import RconClient
from panel.log_parser import ParsedLogLine, parse_log_line
from panel.player_manager import PlayerEntry, PlayerManager
from panel.screens.console import ConsoleScreen
from panel.screens.dashboard import DashboardScreen
from panel.screens.logs import LogsScreen
from panel.screens.players import PlayersScreen


@dataclass(slots=True)
class PanelState:
    running: bool = False
    uptime: str = "Offline"
    address: str | None = None
    players: list[PlayerEntry] = field(default_factory=list)
    last_overview_refresh: float = 0.0
    last_players_refresh: float = 0.0

    @property
    def player_count(self) -> int:
        return len(self.players)


class PanelServices:
    def __init__(self) -> None:
        self.config = load_config()
        self.root_dir = Path(__file__).resolve().parent.parent
        self.docker_manager = DockerManager(
            compose_dir=self.config.docker_compose_dir,
            container_name=self.config.docker_container_name,
            service_name=self.config.docker_service_name,
            dependent_service_names=[self.config.playit_service_name],
        )
        self.rcon_client = RconClient(
            host=self.config.rcon_host,
            port=self.config.rcon_port,
            password=self.config.rcon_password,
            retries=self.config.rcon_retries,
            retry_delay=self.config.rcon_retry_delay,
        )
        self.playit_client = PlayitClient(
            container_name=self.config.playit_container_name,
            fallback_address=self.config.playit_tunnel_address,
        )
        self.player_manager = PlayerManager(self.rcon_client)
        self.audit_dir = self.root_dir / ".audentity"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log = self.audit_dir / "panel_audit.log"
        self.app: AdminPanelApp | None = None
        self._address_cache: str | None = None
        self._address_cache_until = 0.0
        self._player_cache: list[PlayerEntry] = []
        self._player_cache_until = 0.0
        self.shutdown_event = Event()

    def fetch_overview(self, *, force_address: bool = False) -> dict[str, Any]:
        running = self.docker_manager.is_running()
        return {
            "running": running,
            "address": self.get_tunnel_address(force=force_address) if running else None,
            "uptime": self._uptime_text() if running else "Offline",
        }

    def fetch_players(self, *, force: bool = False) -> list[PlayerEntry]:
        now = time.monotonic()
        if not force and now < self._player_cache_until:
            return list(self._player_cache)

        if not self.docker_manager.is_running():
            self._player_cache = []
            self._player_cache_until = now + 3
            return []

        players = self.player_manager.list_players()
        self._player_cache = players
        self._player_cache_until = now + 5
        return list(players)

    def invalidate_players(self) -> None:
        self._player_cache_until = 0.0

    def get_tunnel_address(self, *, force: bool = False) -> str | None:
        now = time.monotonic()
        if not force and now < self._address_cache_until:
            return self._address_cache

        self._address_cache = self.playit_client.get_tunnel_address()
        self._address_cache_until = now + 30
        return self._address_cache

    def invalidate_address(self) -> None:
        self._address_cache_until = 0.0

    def _uptime_text(self) -> str:
        container = self.docker_manager.get_container()
        if container is None:
            return "Offline"
        try:
            container.reload()
            started_at = container.attrs["State"]["StartedAt"]
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            delta = datetime.now(start_dt.tzinfo) - start_dt
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours}h {minutes}m"
        except Exception:  # noqa: BLE001
            return "Unknown"

    def player_details(self, player: str) -> str:
        return self.player_manager.player_details(player)

    def player_action(self, action: str, player: str, payload: str = "") -> str:
        mapping = {
            "kick": lambda: self.player_manager.kick(player, payload or "Removed by admin panel"),
            "ban": lambda: self.player_manager.ban(player, payload or "Banned by admin panel"),
            "message": lambda: self.player_manager.message(player, payload),
            "whitelist_add": lambda: self.player_manager.whitelist_add(player),
            "whitelist_remove": lambda: self.player_manager.whitelist_remove(player),
        }
        response = mapping[action]()
        self.invalidate_players()
        self.audit(f"{action} {player} -> {response}")
        return response

    def toggle_op(self, player: str) -> str:
        response = self.player_manager.op(player)
        self.invalidate_players()
        self.audit(f"toggle-op {player} -> {response}")
        return response

    def send_command(self, command: str) -> str:
        response = self.rcon_client.command(command)
        self.audit(f"command {command} -> {response}")
        return response

    def safe_rcon(self, command: str) -> str:
        try:
            response = self.rcon_client.command(command)
            self.audit(f"command {command} -> {response}")
            return response
        except Exception as exc:  # noqa: BLE001
            self.audit(f"command {command} -> ERROR {exc}")
            return str(exc)

    def notify(self, message: str) -> None:
        if self.app is not None:
            self.app.notify(message)

    def audit(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.audit_log.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")

    def start_stack(self) -> str:
        self.docker_manager.start()
        self.invalidate_players()
        self.invalidate_address()
        self.audit("stack start")
        return "Server stack started."

    def stop_stack(self) -> str:
        self.docker_manager.stop(timeout=60)
        self.invalidate_players()
        self.invalidate_address()
        self.audit("stack stop")
        return "Server stack stopped."

    def restart_stack(self) -> str:
        self.docker_manager.stop(timeout=60)
        self.docker_manager.start()
        self.invalidate_players()
        self.invalidate_address()
        self.audit("stack restart")
        return "Server stack restarted."

    def stream_logs(self, queue: SimpleQueue[ParsedLogLine]) -> None:
        log_path = self.root_dir / "server" / "data" / "logs" / "latest.log"
        position = 0

        while not self.shutdown_event.is_set():
            if not log_path.exists():
                self.shutdown_event.wait(2)
                continue

            try:
                size = log_path.stat().st_size
                if position > size:
                    position = 0

                with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(position)
                    while True:
                        if self.shutdown_event.is_set():
                            return
                        line = handle.readline()
                        if not line:
                            position = handle.tell()
                            self.shutdown_event.wait(0.25)
                            current_size = log_path.stat().st_size if log_path.exists() else 0
                            if current_size < position:
                                position = 0
                                break
                            continue
                        queue.put(parse_log_line(line))
            except Exception:  # noqa: BLE001
                self.shutdown_event.wait(2)

    def shutdown(self) -> None:
        self.shutdown_event.set()


class AdminPanelApp(App):
    CSS_PATH = str(Path(__file__).with_name("theme.tcss"))
    BINDINGS = [
        ("1", "show_tab('dashboard')", "Dashboard"),
        ("2", "show_tab('players')", "Players"),
        ("3", "show_tab('console')", "Console"),
        ("4", "show_tab('logs')", "Logs"),
        ("tab", "next_tab", "Next tab"),
        ("shift+tab", "previous_tab", "Previous tab"),
        ("s", "start_stack", "Start stack"),
        ("t", "stop_stack", "Stop stack"),
        ("r", "restart_stack", "Restart stack"),
        ("question_mark", "help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.services = PanelServices()
        self.services.app = self
        self.state = PanelState()
        self.dashboard_screen = DashboardScreen(self.services, id="dashboard-screen")
        self.players_screen = PlayersScreen(self.services, id="players-screen")
        self.console_screen = ConsoleScreen(self.services, id="console-screen")
        self.logs_screen = LogsScreen(self.services, id="logs-screen")
        self._refreshing_overview = False
        self._refreshing_players = False
        self._stack_action_in_progress = False
        self._log_queue: SimpleQueue[ParsedLogLine] = SimpleQueue()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Audentity Runner - Initializing...", id="status-line")
        with TabbedContent(id="tabs"):
            with TabPane("Dashboard", id="dashboard"):
                yield self.dashboard_screen
            with TabPane("Players", id="players"):
                yield self.players_screen
            with TabPane("Console", id="console"):
                yield self.console_screen
            with TabPane("Logs", id="logs"):
                yield self.logs_screen
        yield Footer()
        yield Static(
            "S start  T stop  R restart  1-4 tabs  ? help  Q quit",
            id="footer-hint",
        )

    async def on_mount(self) -> None:
        await self.refresh_overview(force_address=True)
        await self.refresh_players(force=True)
        self.set_interval(8, self.refresh_overview)
        self.set_interval(5, self.refresh_players)
        self.set_interval(0.25, self._drain_logs)
        self.run_worker(self._log_worker, exclusive=True, thread=True)

    async def refresh_overview(self, force_address: bool = False) -> None:
        if self._refreshing_overview or self._stack_action_in_progress:
            return

        self._refreshing_overview = True
        try:
            overview = await asyncio.to_thread(self.services.fetch_overview, force_address=force_address)
            self.state.running = overview["running"]
            self.state.uptime = overview["uptime"]
            self.state.address = overview["address"]
            self.state.last_overview_refresh = time.monotonic()
            self._update_status_line()
            if self.query_one("#tabs", TabbedContent).active == "dashboard":
                self.dashboard_screen.apply_state(self.state)
        finally:
            self._refreshing_overview = False

    async def refresh_players(self, force: bool = False) -> None:
        if self._refreshing_players or self._stack_action_in_progress:
            return

        self._refreshing_players = True
        try:
            players = await asyncio.to_thread(self.services.fetch_players, force=force)
            self.state.players = players
            self.state.last_players_refresh = time.monotonic()
            if self.query_one("#tabs", TabbedContent).active == "dashboard":
                self.dashboard_screen.apply_state(self.state)
            if self.query_one("#tabs", TabbedContent).active == "players":
                await self.players_screen.apply_players(players)
        finally:
            self._refreshing_players = False

    def _update_status_line(self) -> None:
        status = "Online" if self.state.running else "Offline"
        address = self.state.address or "Unavailable"
        self.query_one("#status-line", Static).update(
            f"Audentity Runner - {status} - {address}"
        )

    def _drain_logs(self) -> None:
        batch: list[ParsedLogLine] = []
        for _ in range(100):
            try:
                batch.append(self._log_queue.get_nowait())
            except Empty:
                break

        if batch:
            self.logs_screen.add_entries(
                batch,
                render=self.query_one("#tabs", TabbedContent).active == "logs",
            )

    def _log_worker(self) -> None:
        try:
            self.services.stream_logs(self._log_queue)
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(self.notify, f"Log stream stopped: {exc}")

    async def action_show_tab(self, tab_id: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab_id
        await self._handle_tab_change(tab_id)

    async def action_next_tab(self) -> None:
        tabs = ["dashboard", "players", "console", "logs"]
        current = self.query_one("#tabs", TabbedContent).active
        index = (tabs.index(current) + 1) % len(tabs)
        next_tab = tabs[index]
        self.query_one("#tabs", TabbedContent).active = next_tab
        await self._handle_tab_change(next_tab)

    async def action_previous_tab(self) -> None:
        tabs = ["dashboard", "players", "console", "logs"]
        current = self.query_one("#tabs", TabbedContent).active
        index = (tabs.index(current) - 1) % len(tabs)
        previous_tab = tabs[index]
        self.query_one("#tabs", TabbedContent).active = previous_tab
        await self._handle_tab_change(previous_tab)

    async def _handle_tab_change(self, tab_id: str) -> None:
        if tab_id == "dashboard":
            self.dashboard_screen.apply_state(self.state)
        elif tab_id == "players":
            if self.state.players:
                await self.players_screen.apply_players(self.state.players)
            await self.refresh_players(force=True)
        elif tab_id == "logs":
            await asyncio.sleep(0)
            self.logs_screen.render_current()

    async def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        await self._handle_tab_change(event.tab.id)

    async def action_start_stack(self) -> None:
        if self._stack_action_in_progress:
            self.notify("Another stack action is already running.")
            return

        self._stack_action_in_progress = True
        try:
            self.notify("Starting server stack...")
            message = await asyncio.to_thread(self.services.start_stack)
            self.notify(message)
            await self.refresh_overview(force_address=True)
            await self.refresh_players(force=True)
        finally:
            self._stack_action_in_progress = False

    async def action_stop_stack(self) -> None:
        if self._stack_action_in_progress:
            self.notify("Another stack action is already running.")
            return

        self._stack_action_in_progress = True
        try:
            self.notify("Stopping server stack...")
            message = await asyncio.to_thread(self.services.stop_stack)
            self.notify(message)
            await self.refresh_overview(force_address=True)
            await self.refresh_players(force=True)
        finally:
            self._stack_action_in_progress = False

    async def action_restart_stack(self) -> None:
        if self._stack_action_in_progress:
            self.notify("Another stack action is already running.")
            return

        self._stack_action_in_progress = True
        try:
            self.notify("Restarting server stack...")
            message = await asyncio.to_thread(self.services.restart_stack)
            self.notify(message)
            await self.refresh_overview(force_address=True)
            await self.refresh_players(force=True)
        finally:
            self._stack_action_in_progress = False

    def action_help(self) -> None:
        self.notify(
            "Tabs: 1-4 or Tab. Stack: S/T/R. Console: Enter sends, Up/Down history, Tab autocomplete.",
            timeout=8,
        )

    def action_quit(self) -> None:
        self.services.shutdown()
        self.exit()

    def on_unmount(self) -> None:
        self.services.shutdown()


def main() -> None:
    AdminPanelApp().run()
