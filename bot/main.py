from __future__ import annotations

import asyncio
import discord
import signal
from discord.ext import commands

from bot.commands import register_commands
from bot.config import load_config
from bot.docker_manager import DockerManager
from bot.playit_client import PlayitClient
from bot.rcon_client import RconClient


def create_bot():
    config = load_config()

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=config.command_prefix, intents=intents)

    docker_manager = DockerManager(
        compose_dir=config.docker_compose_dir,
        container_name=config.docker_container_name,
        service_name=config.docker_service_name,
        dependent_service_names=[config.playit_service_name],
    )
    rcon_client = RconClient(
        host=config.rcon_host,
        port=config.rcon_port,
        password=config.rcon_password,
        retries=config.rcon_retries,
        retry_delay=config.rcon_retry_delay,
    )
    playit_client = PlayitClient(
        container_name=config.playit_container_name,
        fallback_address=config.playit_tunnel_address,
    )

    @bot.event
    async def on_ready():
        print(f"Bot logged in as {bot.user}")
        print(f"Compose directory: {config.docker_compose_dir}")
        print(f"Target container: {config.docker_container_name}")
        await bot.change_presence(activity=discord.Game(name="Audentity Runner"))

    register_commands(bot, config, docker_manager, rcon_client, playit_client)
    return bot, config


async def run_bot() -> None:
    bot, config = create_bot()

    if not config.discord_token:
        raise SystemExit("ERROR: DISCORD_TOKEN is not configured.")

    print("Starting Audentity Runner...")

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def request_shutdown() -> None:
        if shutdown_event.is_set():
            return
        print("Shutdown signal received. Closing Discord bot...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_args: request_shutdown())

    bot_task = asyncio.create_task(bot.start(config.discord_token))
    wait_task = asyncio.create_task(shutdown_event.wait())

    try:
        done, _pending = await asyncio.wait(
            {bot_task, wait_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if wait_task in done and not bot_task.done():
            await bot.close()
            await bot_task
        elif bot_task in done:
            await bot_task
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except NotImplementedError:
                signal.signal(sig, signal.SIG_DFL)
        if not bot.is_closed():
            await bot.close()


def main():
    asyncio.run(run_bot())
