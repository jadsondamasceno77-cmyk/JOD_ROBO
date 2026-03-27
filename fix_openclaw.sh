#!/bin/bash
# 🦞 OpenClaw Fix Script - Resolving Gateway Auth & Ollama Hangs

echo "1. Corrigindo chave de autenticação (enabled -> mode)..."
# O erro 'Unrecognized key: enabled' ocorre porque a versão atual usa 'mode'
openclaw config set gateway.auth.mode none
openclaw config set gateway.mode local

echo "2. Sincronizando serviço de gateway..."
# O comando --force garante que o environment do systemd (ou similar) seja atualizado
openclaw gateway install --force 2>/dev/null || echo "Aviso: 'gateway install' ignorado (ambiente sem systemd)"

echo "3. Reiniciando Gateway..."
openclaw gateway restart

echo "4. Verificando conectividade com Ollama..."
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null; then
  echo "⚠️  ALERTA: Ollama não detectado em 127.0.0.1:11434"
  echo "O comando 'openclaw agent' vai TRAVAR em 'Waiting for agent reply' se o Ollama não estiver rodando."
  echo "Inicie o Ollama primeiro: 'ollama serve'"
else
  echo "✅ Ollama detectado!"
fi

echo "5. Testando agente (timeout 30s para evitar travamentos longos)..."
openclaw agent --agent main --message "oi" --timeout 30 2>&1 | grep -E "Waiting|Error|Failover"
