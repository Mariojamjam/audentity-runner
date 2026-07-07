from __future__ import annotations

import discord

from bot.docker_manager import DockerManagerError
from bot.permissions import is_authorized
from bot.rcon_client import RconError


def register_ingame_commands(bot, config, docker_manager, rcon_client, playit_client):
    @bot.command(name="say")
    @is_authorized(config.authorized_user_ids)
    async def say_command(ctx, *, message: str):
        try:
            rcon_client.command(f"say {message}")
            await ctx.send("Message sent to the server.")
        except RconError as exc:
            await ctx.send(str(exc))

    @bot.command(name="players")
    @is_authorized(config.authorized_user_ids)
    async def players_command(ctx):
        try:
            response = rcon_client.command("list") or "No response from the server."
            await ctx.send(response)
        except RconError as exc:
            await ctx.send(str(exc))

    @bot.command(name="whitelist")
    @is_authorized(config.authorized_user_ids)
    async def whitelist_command(ctx, player: str):
        try:
            response = rcon_client.command(f"whitelist add {player}")
            await ctx.send(response or f"{player} added to the whitelist.")
        except RconError as exc:
            await ctx.send(str(exc))

    @bot.command(name="address")
    @is_authorized(config.authorized_user_ids)
    async def address_command(ctx):
        address = playit_client.get_tunnel_address()
        try:
            running = docker_manager.is_running()
        except DockerManagerError as exc:
            await ctx.send(str(exc))
            return

        if address:
            status = "online" if running else "offline"
            await ctx.send(f"Server address: `{address}` (server {status})")
            return

        await ctx.send("Could not retrieve the tunnel address right now.")

    @bot.command(name="commands")
    async def help_command(ctx):
        embed = discord.Embed(
            title="Audentity Runner Commands",
            description="Manage the Minecraft server remotely through Audentity Runner.",
            color=0x00AAFF,
        )
        embed.add_field(name="!R:start", value="Start the server stack", inline=False)
        embed.add_field(name="!R:stop", value="Stop the server stack", inline=False)
        embed.add_field(name="!R:status", value="Show server status", inline=False)
        embed.add_field(name="!R:restart", value="Restart the server stack", inline=False)
        embed.add_field(name="!R:address", value="Show the public Playit address", inline=False)
        embed.add_field(name="!R:say <message>", value="Send a message to in-game chat", inline=False)
        embed.add_field(name="!R:players", value="List online players", inline=False)
        embed.add_field(name="!R:whitelist <player>", value="Add a player to the whitelist", inline=False)
        embed.add_field(name="!R:commands", value="Show this help message", inline=False)
        await ctx.send(embed=embed)
