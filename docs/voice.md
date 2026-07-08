# How To Enable In-Game Voice Chat

This guide explains how to enable proximity-based voice chat on the
Minecraft server using the Simple Voice Chat mod.

## 1. Install the mod on the server

This project does not install the voice chat mod automatically.

You must place the correct server-side `.jar` file manually in:

- [server/data/mods](/C:/Users/Pichau/Documents/PastaJam/Codigo/server-runner/server-runner-bot/server/data/mods:1)

This is not necessary if the imported modpack already has the voice mod.

Make sure the mod version matches:

- your Minecraft version
- your loader (`TYPE=FABRIC`, `TYPE=FORGE`, or `TYPE=NEOFORGE`)

## 2. Enable the environment variables

Open your root `.env` and set:

```env
VOICE_CHAT_ENABLED=TRUE
VOICE_CHAT_PORT=24454
VOICE_CHAT_TUNNEL_ADDRESS=
```

Notes:

- `VOICE_CHAT_ENABLED=TRUE` means you intend to use Simple Voice Chat.
- `VOICE_CHAT_PORT=24454` is the default mod port.
- `VOICE_CHAT_TUNNEL_ADDRESS` must be filled after you create the UDP tunnel in Playit.

## 3. Port exposure

The Docker stack already exposes the UDP voice chat port through:

```yaml
- "${VOICE_CHAT_PORT:-24454}:${VOICE_CHAT_PORT:-24454}/udp"
```

You do not need to edit `docker-compose.yml` to enable or disable voice chat.
Only `.env` changes are required.

## 4. Create a dedicated UDP tunnel in Playit

Voice chat uses a separate UDP tunnel from the main Minecraft TCP tunnel.

In Playit:

1. Open the Playit dashboard.
2. Create a new tunnel.
3. Choose `UDP` as the tunnel type 
4. Select port count as 1
5. Follow the security steps
6. Chose the public endpoint
7. Select the same Docker agent used by this project.
8. Set the local port to the same value as `VOICE_CHAT_PORT`.
9. Save the tunnel.

After the tunnel is created:

1. Open the `Tunnels` tab in Playit.
2. Copy the public `address:port` shown for the UDP tunnel.
3. Paste it into `.env`:

```env
VOICE_CHAT_TUNNEL_ADDRESS=your-voice-address.playit.gg:12345
```

## 5. Point the mod configuration to the tunnel

This project can manage the voice chat config automatically from `.env`.

The Docker stack mounts a managed template into `/config`, and the
`itzg/minecraft-server` image replaces `${CFG_...}` placeholders during sync.
That means `VOICE_CHAT_TUNNEL_ADDRESS` from `.env` is written into:

- `server/data/config/voicechat/voicechat-server.properties`

So if:

```env
VOICE_CHAT_PORT=24454
VOICE_CHAT_TUNNEL_ADDRESS=your-voice-address.playit.gg:12345
```

then the synced config will automatically contain:

```properties
port=24454
voice_host=your-voice-address.playit.gg:12345
```

The important rule is still the same:

- the mod must advertise the public Playit UDP tunnel address, not `127.0.0.1`
- the port must match the UDP tunnel you created

## 6. Restart and verify

Restart the stack after:

- placing the server mod
- setting the `.env` values
- creating the UDP tunnel
- updating the voice chat config

Useful check:

```bash
docker compose --env-file .env -f docker-compose.yml logs --tail=100 minecraft
```

Look for a log line indicating that the voice chat server started on the configured port.

## 7. Client-side requirement

Every player must also install the matching Simple Voice Chat mod on their own client.

Without the client mod:

- the server still runs normally
- Minecraft login still works
- voice chat will not work for that player

## 8. Troubleshooting

- If Minecraft works but voice chat does not, confirm the Playit tunnel is `UDP`, not `TCP`.
- Confirm `VOICE_CHAT_PORT` matches both the Docker-exposed port and the Playit local port.
- Confirm the server-side mod and each client-side mod match the server version and loader.
- Confirm the voice chat config is advertising the public Playit tunnel address, not a local host address.
