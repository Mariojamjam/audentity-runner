from __future__ import annotations

import subprocess
from pathlib import Path

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

    def _compose_command(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "--env-file",
            str(self.compose_env_file),
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

    def start(self):
        try:
            subprocess.run(
                self._compose_command("up", "-d", *self._service_names()),
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

        container = self.get_container()
        if container is None:
            raise DockerManagerError("The Minecraft container was not found after docker compose up.")
        return container

    def stop(self, timeout: int = 60):
        container = self.get_container()
        if container is None:
            return False

        try:
            subprocess.run(
                self._compose_command("stop", "-t", str(timeout), *self._service_names()),
                cwd=self.compose_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise DockerManagerError(f"Failed to stop the stack: {detail}") from exc

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
