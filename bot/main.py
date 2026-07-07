from __future__ import annotations

import discord
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


def main():
    bot, config = create_bot()

    if not config.discord_token:
        raise SystemExit("ERROR: DISCORD_TOKEN is not configured.")

    print("Starting Audentity Runner...")
    bot.run(config.discord_token)
