#!/bin/bash
# Fix a wedged docker engine in WSL (no systemd): kill exact-name daemons,
# clear stale sockets, start one clean instance, wait for socket (max 25s).
# Usage: bash /mnt/f/netflix-movie-recommendation-system/scripts/wsl_engine_fix.sh
set -u
if docker ps >/dev/null 2>&1; then
  echo "ENGINE_ALREADY_UP"
  docker ps --format 'TABLE {{.Names}}\t{{.Status}}'
  exit 0
fi
pkill -9 -x dockerd 2>/dev/null
pkill -9 -x containerd 2>/dev/null
sleep 2
rm -f /var/run/docker.sock /var/run/docker.pid
rm -f /var/lib/docker/network/files/local-kv.db
echo "cleaned stale network db"
nohup /usr/bin/dockerd >/tmp/engine.log 2>&1 &
echo "LAUNCHED pid=$!"
for i in $(seq 1 25); do
  if docker ps >/dev/null 2>&1; then
    echo "ENGINE_UP after ${i}s"
    docker ps --format 'TABLE {{.Names}}\t{{.Status}}'
    exit 0
  fi
  echo "waiting ${i}s..."
  sleep 1
done
echo "ENGINE_FAILED"
tail -n 20 /tmp/engine.log
exit 1
