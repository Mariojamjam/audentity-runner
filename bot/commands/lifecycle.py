from __future__ import annotations

import asyncio

import discord

from bot.docker_manager import DockerManagerError
from bot.permissions import is_authorized
from bot.rcon_client import RconError


def _format_address(address: str | None) -> str:
    return address or "Unavailable"


def register_lifecycle_commands(bot, config, docker_manager, rcon_client, playit_client):
    @bot.command(name="start")
    @is_authorized(config.authorized_user_ids)
    async def start_server(ctx):
        try:
            if docker_manager.is_running():
                await ctx.send("The server is already running.")
                address = playit_client.get_tunnel_address()
                if address:
                    await ctx.send(f"Server address: {address}")
                return

            await ctx.send("Starting server...")
            docker_manager.start()
            await ctx.send("Server started.")
            address = playit_client.get_tunnel_address()
            if address:
                await ctx.send(f"Server address: {address}")
            await ctx.send("Wait a few seconds for the server to finish loading.")
        except DockerManagerError as exc:
            await ctx.send(str(exc))

    @bot.command(name="stop")
    @is_authorized(config.authorized_user_ids)
    async def stop_server(ctx):
        try:
            if not docker_manager.is_running():
                await ctx.send("The server is not running.")
                return
        except DockerManagerError as exc:
            await ctx.send(str(exc))
            return

        await ctx.send("Stopping server...")

        try:
            rcon_client.graceful_stop()
        except RconError:
            await ctx.send("RCON is unavailable. Falling back to docker stop.")

        try:
            docker_manager.stop(timeout=60)
            await ctx.send("Server stopped.")
        except DockerManagerError as exc:
            await ctx.send(str(exc))

    @bot.command(name="status")
    @is_authorized(config.authorized_user_ids)
    async def check_status(ctx):
        try:
            running = docker_manager.is_running()
        except DockerManagerError as exc:
            await ctx.send(str(exc))
            return

        address = playit_client.get_tunnel_address()

        if running:
            embed = discord.Embed(title="Server Status", color=0x00FF00)
            embed.add_field(name="Status", value="Online", inline=False)
            embed.add_field(name="Address", value=_format_address(address), inline=False)
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="Server Status", color=0xFF0000)
        embed.add_field(name="Status", value="Offline", inline=False)
        embed.add_field(name="Address", value=_format_address(address), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="restart")
    @is_authorized(config.authorized_user_ids)
    async def restart_server(ctx):
        await ctx.send("Restarting server...")

        try:
            if docker_manager.is_running():
                try:
                    rcon_client.graceful_stop()
                except RconError:
                    await ctx.send("RCON is unavailable. Falling back to docker stop.")

                docker_manager.stop(timeout=60)
                await ctx.send("Server stopped. Waiting 5 seconds...")
                await asyncio.sleep(5)

            docker_manager.start()
            await ctx.send("Server restarted.")
            address = playit_client.get_tunnel_address()
            if address:
                await ctx.send(f"Server address: {address}")
        except DockerManagerError as exc:
            await ctx.send(str(exc))
