#!/bin/bash
# 🦞 OpenClaw Fix Script - Resolving Gateway Auth & Ollama Hangs

echo "1. Correcting authentication key (enabled -> mode)..."
# The error 'Unrecognized key: enabled' occurs because the current version uses 'mode'
openclaw config set gateway.auth.mode none
openclaw config set gateway.mode local

echo "2. Syncing gateway service..."
# The --force command ensures the systemd environment (or similar) is updated
openclaw gateway install --force 2>/dev/null || echo "Warning: 'gateway install' skipped (non-systemd environment)"

echo "3. Restarting Gateway..."
openclaw gateway restart

echo "4. Verifying Ollama connectivity..."
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null; then
  echo "⚠️  ALERT: Ollama not detected at 127.0.0.1:11434"
  echo "The 'openclaw agent' command will HANG at 'Waiting for agent reply' if Ollama is not running."
  echo "Start Ollama first: 'ollama serve'"
else
  echo "✅ Ollama detected!"
  if ! curl -s http://127.0.0.1:11434/api/tags | grep -q "llama3.2:1b"; then
    echo "⚠️  WARNING: Model 'llama3.2:1b' not found in Ollama."
    echo "Run: 'ollama pull llama3.2:1b' to ensure OpenClaw works correctly."
  else
    echo "✅ Model 'llama3.2:1b' is ready."
  fi
fi

echo "5. Testing agent (30s timeout to avoid long hangs)..."
openclaw agent --agent main --message "hi" --timeout 30 2>&1 | grep -E "Waiting|Error|Failover"

echo "------------------------------------------------------------"
echo "If OpenClaw still hangs at 'Waiting for agent reply', run:"
echo "  openclaw logs --follow"
echo "in a separate terminal to diagnose the issue in real-time."
