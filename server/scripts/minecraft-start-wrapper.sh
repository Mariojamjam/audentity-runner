#!/bin/sh
set -eu

SERVER_PROPERTIES="/data/server.properties"

if [ -n "${LEVEL:-}" ]; then
  mkdir -p /data

  if [ -f "$SERVER_PROPERTIES" ]; then
    if grep -q '^level-name=' "$SERVER_PROPERTIES"; then
      sed -i "s/^level-name=.*/level-name=${LEVEL}/" "$SERVER_PROPERTIES"
    else
      printf '\nlevel-name=%s\n' "$LEVEL" >> "$SERVER_PROPERTIES"
    fi
    echo "[audentity] Enforced level-name=${LEVEL} in /data/server.properties"
  else
    echo "[audentity] LEVEL=${LEVEL} will be applied when server.properties is created"
  fi
fi

exec /image/scripts/start
