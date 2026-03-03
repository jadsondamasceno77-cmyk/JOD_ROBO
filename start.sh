#!/bin/sh
set -eu

# tenta entrar na pasta do app (pelo log do Railpack: ./aplicativo/)
if [ -d "/workspace/aplicativo" ]; then
  cd /workspace/aplicativo
elif [ -d "./aplicativo" ]; then
  cd ./aplicativo
fi

PORT="${PORT:-8000}"
echo "[JOD_ROBO] Iniciando API em 0.0.0.0:${PORT}"
echo "[JOD_ROBO] Diretório atual: $(pwd)"

# escolhe automaticamente o entrypoint do FastAPI
if [ -f "app/main.py" ]; then
  TARGET="app.main:app"
elif [ -f "main.py" ]; then
  TARGET="main:app"
else
  echo "[ERRO] Não achei app/main.py nem main.py no diretório atual."
  echo "[ERRO] Conteúdo:"
  ls -la
  exit 1
fi

echo "[JOD_ROBO] Uvicorn target: ${TARGET}"
exec uvicorn "${TARGET}" --host 0.0.0.0 --port "${PORT}"
