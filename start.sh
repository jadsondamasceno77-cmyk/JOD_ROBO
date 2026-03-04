#!/bin/sh
set -eu

# Diretório onde este script está (no Railway/Docker costuma ser /workspace)
BASE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

PORT="${PORT:-8000}"

echo "[JOD_ROBO] Iniciando API em 0.0.0.0:${PORT}"
echo "[JOD_ROBO] BASE_DIR: ${BASE_DIR}"

# Procura o código no lugar certo:
# 1) raiz (BASE_DIR)
# 2) BASE_DIR/aplicativo (se existir e tiver o app)
FOUND_DIR=""

for d in "${BASE_DIR}" "${BASE_DIR}/aplicativo"; do
  if [ -f "${d}/app/main.py" ] || [ -f "${d}/main.py" ]; then
    FOUND_DIR="${d}"
    break
  fi
done

if [ -z "${FOUND_DIR}" ]; then
  echo "[ERRO] Não encontrei app/main.py nem main.py em:"
  echo " - ${BASE_DIR}"
  echo " - ${BASE_DIR}/aplicativo"
  echo "[ERRO] Listando ${BASE_DIR}:"
  ls -la "${BASE_DIR}" || true
  echo "[ERRO] Listando ${BASE_DIR}/aplicativo:"
  ls -la "${BASE_DIR}/aplicativo" 2>/dev/null || true
  exit 1
fi

cd "${FOUND_DIR}"
echo "[JOD_ROBO] Diretório de execução: $(pwd)"

if [ -f "app/main.py" ]; then
  TARGET="app.main:app"
elif [ -f "main.py" ]; then
  TARGET="main:app"
else
  echo "[ERRO] Encontrou diretório mas não encontrou app/main.py nem main.py após cd."
  ls -la
  exit 1
fi

echo "[JOD_ROBO] Uvicorn target: ${TARGET}"
exec uvicorn "${TARGET}" --host 0.0.0.0 --port "${PORT}"
