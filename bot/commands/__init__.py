from .ingame import register_ingame_commands
from .lifecycle import register_lifecycle_commands


def register_commands(bot, config, docker_manager, rcon_client, playit_client):
    register_lifecycle_commands(bot, config, docker_manager, rcon_client, playit_client)
    register_ingame_commands(bot, config, docker_manager, rcon_client, playit_client)
