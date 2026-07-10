from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import docker
from docker.errors import APIError, DockerException, NotFound


class DockerManagerError(RuntimeError):
    """Raised when Docker cannot complete an operation."""


class DockerManager:
    def __init__(
        self,
        compose_dir: Path,
        container_name: str,
        service_name: str,
        dependent_service_names: list[str] | None = None,
    ):
        self.compose_dir = compose_dir
        self.container_name = container_name
        self.service_name = service_name
        self.dependent_service_names = dependent_service_names or []
        self.compose_env_file = self.compose_dir / ".env"
        self.compose_file = self.compose_dir / "docker-compose.yml"

    def _compose_command(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "--env-file",
            str(self.compose_env_file),
            "-f",
            str(self.compose_file),
            *args,
        ]

    def _service_names(self) -> list[str]:
        return [self.service_name, *self.dependent_service_names]

    def _client(self):
        try:
            return docker.from_env()
        except DockerException as exc:
            raise DockerManagerError(
                "Could not connect to Docker. Make sure Docker Desktop is running."
            ) from exc

    def get_container(self):
        client = self._client()
        try:
            return client.containers.get(self.container_name)
        except NotFound:
            return None
        except APIError as exc:
            raise DockerManagerError(f"Failed to inspect the container: {exc.explanation}") from exc

    def _get_service_containers(self):
        client = self._client()
        containers = []
        for name in [self.container_name, *self._dependent_container_names()]:
            try:
                containers.append(client.containers.get(name))
            except NotFound:
                return None
            except APIError as exc:
                raise DockerManagerError(f"Failed to inspect container '{name}': {exc.explanation}") from exc
        return containers

    def _dependent_container_names(self) -> list[str]:
        mapping = {
            "playit": "playit-agent",
            "bot": "audentity-bot",
        }
        return [mapping.get(name, name) for name in self.dependent_service_names]

    def _discover_host_project_root(self) -> str | None:
        container_id = os.environ.get("HOSTNAME")
        if not container_id:
            return None

        try:
            current_container = self._client().containers.get(container_id)
        except (NotFound, APIError, DockerException):
            return None

        for mount in current_container.attrs.get("Mounts", []):
            if mount.get("Destination") == "/app":
                source = mount.get("Source")
                if isinstance(source, str) and source:
                    return source
        return None

    def _expected_minecraft_data_source(self) -> str | None:
        host_root = self._discover_host_project_root()
        if not host_root:
            return None
        return self._join_host_path(host_root, "server", "data")

    def _stack_uses_expected_host_paths(self, containers) -> bool:
        expected_data_source = self._expected_minecraft_data_source()
        if not expected_data_source:
            return True

        for container in containers:
            if container.name != self.container_name:
                continue
            for mount in container.attrs.get("Mounts", []):
                if mount.get("Destination") == "/data":
                    return mount.get("Source") == expected_data_source
        return True

    @staticmethod
    def _join_host_path(root: str, *parts: str) -> str:
        if re.match(r"^[A-Za-z]:\\", root):
            path = PureWindowsPath(root)
            for part in parts:
                path /= part
            return str(path)

        path = PurePosixPath(root)
        for part in parts:
            path /= part
        return str(path)

    @staticmethod
    def _quote_yaml(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _compose_command_with_host_override(self, *args: str) -> tuple[list[str], str | None]:
        host_root = self._discover_host_project_root()
        if not host_root:
            return self._compose_command(*args), None

        override_content = "\n".join(
            [
                "services:",
                "  minecraft:",
                "    volumes:",
                f"      - {self._quote_yaml(self._join_host_path(host_root, 'server', 'data') + ':/data')}",
                f"      - {self._quote_yaml(self._join_host_path(host_root, 'server', 'config') + ':/config:ro')}",
                f"      - {self._quote_yaml(self._join_host_path(host_root, 'server', 'modpacks') + ':/modpacks:ro')}",
                "  bot:",
                "    volumes:",
                f"      - {self._quote_yaml(host_root + ':/app')}",
                "      - '/var/run/docker.sock:/var/run/docker.sock'",
                "",
            ]
        )

        handle = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yml",
            prefix="audentity-compose-",
            delete=False,
            encoding="utf-8",
        )
        try:
            handle.write(override_content)
            handle.flush()
            return (
                [
                    "docker",
                    "compose",
                    "--env-file",
                    str(self.compose_env_file),
                    "-f",
                    str(self.compose_file),
                    "-f",
                    handle.name,
                    *args,
                ],
                handle.name,
            )
        finally:
            handle.close()

    def start(self):
        containers = self._get_service_containers()
        if containers is not None and self._stack_uses_expected_host_paths(containers):
            try:
                for container in containers:
                    container.reload()
                    if container.status != "running":
                        container.start()
            except APIError as exc:
                raise DockerManagerError(f"Failed to start the stack: {exc.explanation}") from exc
        else:
            override_path = None
            try:
                command, override_path = self._compose_command_with_host_override("up", "-d", *self._service_names())
                subprocess.run(
                    command,
                    cwd=self.compose_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise DockerManagerError("Docker Compose was not found in PATH.") from exc
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
                raise DockerManagerError(f"Failed to start the stack: {detail}") from exc
            finally:
                if override_path:
                    try:
                        os.unlink(override_path)
                    except OSError:
                        pass

        container = self.get_container()
        if container is None:
            raise DockerManagerError("The Minecraft container was not found after docker compose up.")
        return container

    def stop(self, timeout: int = 60):
        containers = self._get_service_containers()
        if containers is None:
            return False

        try:
            for container in reversed(containers):
                container.reload()
                if container.status == "running":
                    container.stop(timeout=timeout)
            return True
        except APIError as exc:
            raise DockerManagerError(f"Failed to stop the stack: {exc.explanation}") from exc

    def is_running(self) -> bool:
        container = self.get_container()
        if container is None:
            return False

        try:
            container.reload()
            return container.status == "running"
        except APIError as exc:
            raise DockerManagerError(f"Failed to read container status: {exc.explanation}") from exc

    def stats(self) -> dict[str, float | int | str]:
        container = self.get_container()
        if container is None:
            return {"status": "not_found", "cpu_percent": 0.0, "memory_mb": 0.0}

        try:
            container.reload()
            raw = container.stats(stream=False)
        except APIError as exc:
            raise DockerManagerError(f"Failed to read container stats: {exc.explanation}") from exc

        cpu_percent = self._calculate_cpu_percent(raw)
        memory_usage = raw.get("memory_stats", {}).get("usage", 0)
        memory_mb = memory_usage / 1024 / 1024

        return {
            "status": container.status,
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
        }

    @staticmethod
    def _calculate_cpu_percent(stats: dict) -> float:
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})

        cpu_total = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        precpu_total = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        system_total = cpu_stats.get("system_cpu_usage", 0)
        presystem_total = precpu_stats.get("system_cpu_usage", 0)
        online_cpus = cpu_stats.get("online_cpus") or len(
            cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or [1]
        )

        cpu_delta = cpu_total - precpu_total
        system_delta = system_total - presystem_total
        if cpu_delta <= 0 or system_delta <= 0:
            return 0.0

        return (cpu_delta / system_delta) * online_cpus * 100
