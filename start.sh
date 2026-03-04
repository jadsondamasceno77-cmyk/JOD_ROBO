#!/bin/sh
set -eu

PORT="${PORT:-8000}"
echo "[JOD_ROBO] Subindo FastAPI em 0.0.0.0:${PORT}"
echo "[JOD_ROBO] pwd=$(pwd)"
echo "[JOD_ROBO] ls -la:"
ls -la || true

# Sempre sobe o app da pasta app/main.py
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips="*"
