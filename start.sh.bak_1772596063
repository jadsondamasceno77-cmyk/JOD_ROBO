#!/usr/bin/env sh
set -eu
PORT="${PORT:-8000}"
echo "[JOD_ROBO] Subindo FastAPI main:app em 0.0.0.0:${PORT}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips="*"
