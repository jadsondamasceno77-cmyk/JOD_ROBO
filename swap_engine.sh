#!/bin/bash
set -e

echo "🔄 Iniciando swap do motor jod_brain 10/10..."
cd ~/JOD_ROBO

# 1. Backup
echo "📦 Criando backup..."
tar -czf backup_pre_swap_$(date +%Y%m%d_%H%M).tar.gz \
  docker-compose.yml app/main.py requirements.txt 2>/dev/null || true

# 2. Para containers antigos
echo "🛑 Parando serviços antigos..."
docker-compose down

# 3. Atualiza Dockerfile
echo "📝 Atualizando Dockerfile.api..."
# (cole o Dockerfile acima em docker/Dockerfile.api)

# 4. Atualiza requirements
echo "📦 Atualizando dependências..."
# (requirements.txt já atualizado)

# 5. Aplica patch --api-mode no jod_brain_main.py
echo "🔧 Aplicando patch --api-mode..."
if grep -q "JOD_API_MODE" jod_brain_main.py; then
    echo "✅ Patch já aplicado"
else
    sed -i 's/if not auto_apply:/if not auto_apply and not os.environ.get("JOD_API_MODE"):/' jod_brain_main.py
    echo "✅ Patch aplicado"
fi

# 6. Build
echo "🏗️ Build do container..."
docker-compose build api

# 7. Sobe serviços
echo "🚀 Subindo serviços..."
docker-compose up -d redis ollama api

# 8. Aguarda
echo "⏳ Aguardando inicialização (20s)..."
sleep 20

# 9. Testa
echo "🧪 Testando health check..."
curl -s http://localhost:37777/health | python3 -m json.tool

echo -e "\n✅ SWAP COMPLETO!"
echo "📊 Verifique com: docker-compose ps"
echo "📝 Logs: docker-compose logs -f api"
