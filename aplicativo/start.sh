#!/bin/sh
set -eu

PORT="${PORT:-8000}"
echo "[JOD_ROBO] Iniciando API em 0.0.0.0:${PORT}"

# NÃO entra em /workspace/aplicativo no chute.
# Procura onde realmente existe app/main.py ou main.py:
FOUND_DIR=""
TARGET=""

for d in "/workspace" "/workspace/aplicativo" "$(pwd)" "./aplicativo"; do
  [ -d "$d" ] || continue

  if [ -f "$d/app/main.py" ]; then
    FOUND_DIR="$d"
    TARGET="app.main:app"
    break
  fi

  if [ -f "$d/main.py" ]; then
    FOUND_DIR="$d"
    TARGET="main:app"
    break
  fi
done

if [ -z "$TARGET" ]; then
  echo "[ERRO] Não encontrei app/main.py nem main.py nos diretórios conhecidos."
  echo "[DEBUG] pwd=$(pwd)"
  echo "[DEBUG] ls -la:"; ls -la || true
  echo "[DEBUG] ls -la app:"; ls -la app 2>/dev/null || true
  echo "[DEBUG] ls -la aplicativo:"; ls -la aplicativo 2>/dev/null || true
  exit 1
fi

cd "$FOUND_DIR"
echo "[JOD_ROBO] Diretório de execução: $(pwd)"
echo "[JOD_ROBO] Uvicorn target: $TARGET"

exec uvicorn "$TARGET" --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips="*"
