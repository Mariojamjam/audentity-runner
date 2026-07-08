# Audentity Runner

Audentity Runner is a self-hosted control layer for running a Minecraft server (Vanilla, Forge, Fabric, or NeoForge) on your own machine and exposing it publicly, without paying for hosting or configuring port forwarding.

It runs three pieces together via Docker Compose: the Minecraft server itself, a Playit.gg agent that opens a public tunnel to it, and a Discord bot that manages both. The bot is the main interface. Commands like !R:start, !R:stop, !R:status, and !R:address let anyone in the Discord server safely control the server's lifecycle and get the current public address, while RCON ensures the world saves properly on stop, so shutdown never relies on a raw process kill.

Use it because it turns start, stop, and finding the address into one-line Discord commands instead of manual docker calls, keeps real machine access restricted to authorized Discord users, and decouples the Minecraft variant from the bot's code entirely. Switching loaders or versions is just an .env change, with no Python involved.

## Overview

This project has 3 runtime pieces:

1. `minecraft-server`
   Runs the actual Minecraft server with the `itzg/minecraft-server` image.
2. `playit-agent`
   Creates the public tunnel so players can connect without manual port forwarding.
3. `audentity-bot`
   Runs `runner.py` inside Docker and controls the stack through the Docker engine.

<br>

Repository structure:

```text
server-runner-bot/
|- bot/                  Python bot code
|- docs/                 Supplementary setup guides
|- panel/                Terminal admin panel package
|- server/
|  |- data/              Persistent Minecraft data
|  |- modpacks/          Private/exported modpack files
|- .env                  Runtime configuration
|- .env.example          Documented environment template
|- docker-compose.yml    Docker stack
|- requirements.txt      Python dependencies
|- admin_panel.py        Terminal admin panel entrypoint
|- runner.py             Discord bot entrypoint used by the bot container
|- setup_playit.py       Playit setup helper
|- audentity.py          All-up / all-down automation
`- audentity             Extensionless launcher for `python audentity ...`
```

## External Docs

- Discord Developer Portal: [https://discord.com/developers/applications](https://discord.com/developers/applications)
- Discord bot token help: [https://support-dev.discord.com/hc/en-us/articles/6470840524311-Why-can-t-I-copy-my-bot-s-token](https://support-dev.discord.com/hc/en-us/articles/6470840524311-Why-can-t-I-copy-my-bot-s-token)
- Playit login: [https://playit.gg/login](https://playit.gg/login)
- Playit setup wizard: [https://playit.gg/account/setup/wizard/new-account/](https://playit.gg/account/setup/wizard/new-account/)
- Playit new tunnel: [https://playit.gg/account/setup/new-tunnel](https://playit.gg/account/setup/new-tunnel)
- Playit support home: [https://playit.gg/support/](https://playit.gg/support/)
- Playit Minecraft setup docs: [https://playit.gg/support/how-to-setup-a-mc-server/](https://playit.gg/support/how-to-setup-a-mc-server/)

## Prerequisites

- Docker installed and working
- Python 3.11 or newer
- A Discord bot token
- A Playit.gg account

Check your tools:

```bash
docker --version
docker compose version
python --version
```

## Discord Bot Mini Guide

Create the Discord bot before running this project:

1. Open the Discord Developer Portal:
   [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Create a new application.
3. Open the `Bot` tab.
4. Add a bot user to the application.
5. Copy or reset the bot token.
6. Put that token in `.env` as `DISCORD_TOKEN`.
7. In the `Bot` settings page, enable `Message Content Intent`.
8. Invite the bot to your server from the `OAuth2 > URL Generator` page.

## Setup

### 1. Install Python packages

From the project root:

```bash
pip install -r requirements.txt
```

### 2. Create `.env`

If `.env` does not exist yet:

```bash
cp .env.example .env
```

On PowerShell:

```powershell
Copy-Item .env.example .env
```

### 3. Edit `.env`

Open the root `.env` and set at least:

```env
DISCORD_TOKEN=your_discord_token_here
AUTHORIZED_USERS=
PLAYIT_TUNNEL_ADDRESS=
PLAYIT_SECRET_KEY=
COMMAND_PREFIX=!R:
RCON_HOST=127.0.0.1
TYPE=NEOFORGE
VERSION=1.21.1
ONLINE_MODE=FALSE
NEOFORGE_VERSION=21.1.72
EULA=TRUE
MEMORY=6G
DIFFICULTY=normal
MOTD=server
MAX_PLAYERS=10
ENABLE_RCON=true
RCON_PASSWORD=change_this
RCON_PORT=25575
RCON_RETRIES=3
RCON_RETRY_DELAY=2
```

Important:

- `DISCORD_TOKEN` must be real.
- `PLAYIT_SECRET_KEY` can be empty before the first Playit setup.
- `PLAYIT_TUNNEL_ADDRESS` should be filled in step 9 with the public address shown in Playit's `Tunnels` tab.
- `RCON_HOST=127.0.0.1` is correct for the local admin panel. The Dockerized bot overrides this internally to `minecraft`.
- `ONLINE_MODE=FALSE` is the default in this project, which allows offline/cracked Minecraft clients.
- `ENABLE_RCON` must stay `true`.
- `RCON_PASSWORD` should be changed.

### 4. Create the Playit Docker agent

Do this in your browser:

1. Open [https://playit.gg/login](https://playit.gg/login)
2. Log in.
3. Open [https://playit.gg/account/setup/wizard/new-account/](https://playit.gg/account/setup/wizard/new-account/)
4. Choose the `Docker` path.
5. Create a Docker agent.
6. Give it any name you want.
7. Continue until Playit shows its Docker instructions.

Playit will show example snippets like:

```bash
docker run --rm -it --net=host -e SECRET_KEY=... ghcr.io/playit-cloud/playit-agent:0.17
```

and:

```yaml
services:
  playit:
    image: ghcr.io/playit-cloud/playit-agent:0.17
    network_mode: host
    environment:
      - SECRET_KEY=...
```

### 5. Copy only the Playit secret key

From the Playit page:

1. Find the value after `SECRET_KEY=`
2. Copy only that value
3. Do not copy the full command
4. Do not paste `docker run`
5. Do not paste YAML

Example:

If Playit shows:

```bash
docker run --rm -it --net=host -e SECRET_KEY=abc123 ghcr.io/playit-cloud/playit-agent:0.17
```

copy only:

```text
abc123
```

Save your Playit secret key immediately. Playit only shows the `SECRET_KEY` once, right after you create the agent. If you lose it, there is no way to retrieve it again, so you will need to delete the agent and create a new one, which also breaks any existing tunnel tied to it. Copy the key into `.env` as `PLAYIT_SECRET_KEY` before doing anything else.

### 6. Run the Playit setup script

From the project root:

```bash
python setup_playit.py
```

The script:

1. Checks Docker
2. Checks `.env`
3. Asks for `PLAYIT_SECRET_KEY` if missing
4. Saves it into `.env`
5. Starts the Playit container
6. Shows recent Playit logs

### 7. Confirm the Playit agent connected

After the script runs, you want logs like:

- `secret key valid`
- `agent registered`

Manual check:

```bash
docker compose --env-file .env -f docker-compose.yml logs -f playit
```

### 8. Create the Playit tunnel

Open:

- [https://playit.gg/account/setup/new-tunnel](https://playit.gg/account/setup/new-tunnel)

Create the tunnel with these exact choices:

1. Create a new tunnel
2. Tunnel type: `TCP`
3. Agent: select the Docker agent created for this project
4. Select the Minecraft edition you want
5. Local port: `25565`
6. Save the tunnel

Important:

- For Minecraft Java, the tunnel type must be `TCP`
- Do not use `HTTP`
- Do not use `HTTPS`
- The agent must be the same Docker agent whose `SECRET_KEY` you copied
- The local port must be `25565`

### 9. Get the public Playit address

After saving the tunnel:

1. Wait a few seconds
2. Open the `Tunnels` tab in Playit
3. Find the tunnel you just created
4. Copy the public address shown there
5. That is the address players should use

Update `.env` with the public address from Playit's `Tunnels` tab:

```env
PLAYIT_TUNNEL_ADDRESS=your-address.playit.gg
```

### 10. Verify the tunnel

Check the logs:

```bash
docker compose --env-file .env -f docker-compose.yml logs --tail=100 playit
```

Healthy signs:

- `agent registered`
- `tunnel running`
- `1 tunnels registered`

If the logs still show:

```text
0 tunnels registered
```

the tunnel was not created correctly or was attached to the wrong Docker agent.

## Start and Stop Everything

Use the Audentity CLI to manage the full stack and the bot together.

### Start everything

```bash
python audentity all-up
```

Equivalent:

```bash
python audentity.py all-up
```

What it does:

1. Starts the Docker stack with `docker compose up -d`
2. Starts the Dockerized Discord bot service

### Stop everything

```bash
python audentity all-down
```

Equivalent:

```bash
python audentity.py all-down
```

What it does:

1. Stops the Docker stack with `docker compose down`

### Manual fallback

If needed, you can still run the pieces manually:

```bash
docker compose --env-file .env -f docker-compose.yml up -d
```

and stop the stack with:

```bash
docker compose --env-file .env -f docker-compose.yml down
```

### Check the stack

```bash
docker compose --env-file .env -f docker-compose.yml ps
```

You want both:

- `minecraft-server`
- `playit-agent`
- `audentity-bot`

## Terminal Admin Panel

The project also includes a local terminal admin panel built with Textual.

Run it from the project root:

```bash
python admin_panel.py
```

What it gives you:

- `Dashboard`: stack status, uptime, player count, public address, and quick actions
- `Players`: inspect online players and send kick, ban, message, op, and whitelist actions
- `Console`: send raw Minecraft commands over RCON with command history and simple autocomplete
- `Logs`: watch live server logs with category filters and search

Keyboard shortcuts:

- `1` to `4`: switch tabs
- `Tab` and `Shift+Tab`: move between tabs
- `S`: start the stack
- `T`: stop the stack
- `R`: restart the stack
- `Q`: quit the panel

The panel uses the same `.env`, Docker stack, RCON connection, and Playit settings as the Discord bot. The panel itself stays local on the host, while the bot runs as a Docker service.

## Discord Test

After everything is up, test:

- `!R:status`
- `!R:address`
- `!R:start`
- `!R:stop`
- `!R:restart`
- `!R:commands`

## Mods And Modpacks

This project supports 4 import paths:

1. Public CurseForge modpacks
2. Public Modrinth modpacks
3. Private or exported packs (`.zip` or `.mrpack`)
4. Loose manual mods

The full setup guide for every supported modpack and mod workflow is in [docs/modpacks.md](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/docs/modpacks.md:1).

The full source of truth is the commented modpack section in [.env.example](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/.env.example:1). Use that file as the reference for which variables to enable.

For loader-based setups, choose the correct server loader in `.env`, for example:

- `TYPE=NEOFORGE`
- `TYPE=FABRIC`
- `TYPE=FORGE`

### Public CurseForge modpacks

Use the `AUTO_CURSEFORGE` recipe from `.env.example`.

- Requires `CF_API_KEY`
- Requires `CF_SLUG`
- Uses the built-in import support from `itzg/minecraft-server`

### Public Modrinth modpacks

Use the `MODRINTH` recipe from `.env.example`.

- No API key required
- Set `MODRINTH_MODPACK` to the slug, project ID, or URL

### Private or exported packs

Use [server/modpacks](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/server/modpacks:1).

- Put exported CurseForge `.zip` files or Modrinth `.mrpack` files there
- Reference them from `.env` with container paths such as `/modpacks/your-pack.zip`
- CurseForge `.zip` imports still require `CF_API_KEY`

### Loose manual mods

The loose mods directory is:

- [server/data/mods](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/server/data/mods:1)

Other important persistent folders are usually:

- [server/data/config](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/server/data/config:1)
- [server/data/world](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/server/data/world:1)
- [server/data/logs](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/server/data/logs:1)

Basic loose-mod workflow:

1. Choose the right `TYPE` in `.env`
2. Start the server once
3. Put the mod `.jar` files into `server/data/mods`
4. Restart the server

### Voice Chat

Simple Voice Chat is supported as an optional feature.

- The mod must be installed manually in `server/data/mods`
- The Docker stack exposes the UDP voice chat port through `.env`
- A separate Playit UDP tunnel is required for voice chat
- `voice_host` can be managed automatically from `.env` on startup

The full walkthrough is in [docs/voice.md](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/docs/voice.md:1).

### World Safety With LEVEL

Changing modpacks, loaders, or Minecraft versions on an existing world can make the save incompatible.

To test a new modpack safely, set `LEVEL` in `.env` to a separate world name, for example:

```env
LEVEL=modpack-test-1
```

Each different `LEVEL` value uses a different world folder inside `server/data`, so you can validate a new pack before moving it to your main world.

## What Each File Is For

- `.env`: all runtime configuration
- `.env.example`: documented environment template
- `docs`: supplementary setup guides such as voice chat
- `docker-compose.yml`: Docker services for Minecraft, Playit, and the Discord bot
- `server/data`: persistent Minecraft files
- `server/modpacks`: local private/exported modpack files mounted into `/modpacks`
- `server/playit-data`: persistent Playit agent state
- `server/backups`: zip backups created from the terminal admin panel
- `setup_playit.py`: one-time or repeated Playit setup helper
- `runner.py`: bot entrypoint used by the Docker bot service
- `admin_panel.py`: Textual terminal admin panel entrypoint
- `panel/`: terminal admin panel package
- `audentity.py`: automated all-up / all-down entrypoint
- `.audentity/panel_audit.log`: audit trail for admin panel actions

## Where Minecraft Data Is Stored

By default:

```yaml
volumes:
  - ./data:/data
```

That means the Minecraft files are stored in:

```text
server/data
```

If you want to store Minecraft data outside the repository, edit `docker-compose.yml`.

Example Windows path:

```yaml
volumes:
  - D:/minecraft-data:/data
```

Example Linux path:

```yaml
volumes:
  - /srv/minecraft-data:/data
```

## Discord Commands

- `!R:start` starts the server stack
- `!R:stop` stops the server stack
- `!R:status` shows online/offline status and address
- `!R:restart` restarts the server stack
- `!R:address` shows the public Playit address
- `!R:say <message>` sends a message to in-game chat
- `!R:players` lists online players
- `!R:whitelist <player>` adds a player to the whitelist
- `!R:commands` shows the help message

## Documentation

Additional setup guides are kept in the `docs/` directory:

- [docs/modpacks.md](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/docs/modpacks.md:1) - how to configure public modpacks, local archives, manual server packs, and loose mods
- [docs/voice.md](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/docs/voice.md:1) - how to enable in-game voice chat
