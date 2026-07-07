from __future__ import annotations

from discord.ext import commands


def is_authorized(authorized_user_ids: list[int]):
    async def predicate(ctx):
        if not authorized_user_ids or ctx.author.id in authorized_user_ids:
            return True

        await ctx.send("You do not have permission to use this command.")
        return False

    return commands.check(predicate)
