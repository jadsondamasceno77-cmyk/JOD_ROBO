#!/bin/bash
set -e

TRUST="jod_robo_trust_2026_secure"
BASE="http://localhost:37777"
N8N_AGENT="http://localhost:37780/execute"

echo "=== FASE A1: CORRIGIR PREDICTIVE_HEALING PORTA 37779→37777 + LOOP CONTÍNUO ==="
sed -i 's/localhost:37779/localhost:37777/g' /home/jod_robo/JOD_ROBO/predictive_healing.py
sed -i 's/LOOP_INTERVAL_MINUTES=5/LOOP_INTERVAL_MINUTES=0/g' /home/jod_robo/JOD_ROBO/.env
echo "✓ predictive_healing corrigido"

echo "=== FASE A2: CORRIGIR TELEGRAM → TOOL_CALLS REAIS ==="
cat > /home/jod_robo/JOD_ROBO/telegram_bot_patch.py << 'PATCH'
import httpx, asyncio

async def executar_n8n(task: str, session_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post("http://localhost:37780/execute", json={
                "task": task,
                "session_id": session_id,
                "channel": "telegram"
            })
            data = r.json()
            return data.get("summary", str(data))
    except Exception as e:
        return f"Erro n8n: {e}"
PATCH
echo "✓ telegram patch criado"

echo "=== FASE A3: CHAOS TESTS ==="
cat > /home/jod_robo/JOD_ROBO/chaos_test.sh << 'CHAOS'
#!/bin/bash
TRUST="jod_robo_trust_2026_secure"
echo "--- TEST 1: Health endpoints ---"
curl -sf https://jodrobo-production.up.railway.app/health/live && echo "Railway live ✓"
curl -sf https://jodrobo-production.up.railway.app/health/ready && echo "Railway ready ✓"
curl -sf http://localhost:37777/health/live -H "x-trust-token: $TRUST" -H "x-request-id: t1" -H "x-idempotency-key: t1" && echo "eli-api live ✓"
curl -sf http://localhost:37780/health && echo "n8n-agent ✓"
curl -sf http://localhost:5678/healthz && echo "n8n ✓"
echo "--- TEST 2: Factory create+validate+activate cycle ---"
ID="chaos_test_$(date +%s)"
TASK=$(curl -sf -X POST -H "Content-Type: application/json" -H "x-trust-token: $TRUST" -H "x-request-id: c1" -H "x-idempotency-key: c1" -d "{\"action_type\":\"create_agent_from_template\",\"parameters\":{\"template_name\":\"executor\",\"new_agent_id\":\"$ID\",\"name\":\"Chaos Test Agent\"}}" http://localhost:37777/agents/create-from-template | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
sleep 3
curl -sf -H "x-trust-token: $TRUST" -H "x-request-id: c2" -H "x-idempotency-key: c2" http://localhost:37777/tasks/$TASK | python3 -m json.tool
echo "--- TEST 3: N8N cognitive execute ---"
curl -sf -X POST -H "Content-Type: application/json" -d '{"task":"liste todos os workflows","session_id":"chaos_test","channel":"chaos"}' http://localhost:37780/execute | python3 -c "import sys,json; d=json.load(sys.stdin); print('n8n cognitive:', d.get('status','?'))"
echo "--- CHAOS TESTS COMPLETOS ---"
CHAOS
chmod +x /home/jod_robo/JOD_ROBO/chaos_test.sh
echo "✓ chaos tests criados"

echo "=== FASE B: FABRICAR 9 AGENTES N8N ==="
AGENTES=("n8n-ai-builder|AI Nodes n8n" "n8n-analyst|Visao de negocio automacao" "n8n-architect|Arquitetura workflows n8n" "n8n-devops|Infraestrutura n8n" "n8n-expert-01|N8N Expert completo" "n8n-expert-02|N8N Expert completo" "n8n-expert-03|N8N Expert completo" "n8n-integrator|Integracoes HTTP webhooks" "n8n-js-expert|JavaScript avancado n8n")

for ITEM in "${AGENTES[@]}"; do
    ID="${ITEM%%|*}"
    NOME="${ITEM##*|}"
    TASK=$(curl -sf -X POST -H "Content-Type: application/json" \
        -H "x-trust-token: $TRUST" \
        -H "x-request-id: $(uuidgen)" \
        -H "x-idempotency-key: $(uuidgen)" \
        -d "{\"action_type\":\"create_agent_from_template\",\"parameters\":{\"template_name\":\"executor\",\"new_agent_id\":\"$ID\",\"name\":\"$NOME\"}}" \
        $BASE/agents/create-from-template | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
    sleep 2
    STATUS=$(curl -sf -H "x-trust-token: $TRUST" -H "x-request-id: $(uuidgen)" -H "x-idempotency-key: $(uuidgen)" $BASE/tasks/$TASK | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    echo "✓ $ID criado — $STATUS"
    VTASK=$(curl -sf -X POST -H "Content-Type: application/json" \
        -H "x-trust-token: $TRUST" \
        -H "x-request-id: $(uuidgen)" \
        -H "x-idempotency-key: $(uuidgen)" \
        -d "{\"action_type\":\"validate_agent\",\"parameters\":{\"agent_id\":\"$ID\"}}" \
        $BASE/agents/validate | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
    sleep 3
    ATASK=$(curl -sf -X POST -H "Content-Type: application/json" \
        -H "x-trust-token: $TRUST" \
        -H "x-request-id: $(uuidgen)" \
        -H "x-idempotency-key: $(uuidgen)" \
        -d "{\"action_type\":\"activate_agent\",\"parameters\":{\"agent_id\":\"$ID\"}}" \
        $BASE/agents/activate | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
    sleep 3
    ASTATUS=$(curl -sf -H "x-trust-token: $TRUST" -H "x-request-id: $(uuidgen)" -H "x-idempotency-key: $(uuidgen)" $BASE/tasks/$ATASK | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    echo "  → $ID ativado — $ASTATUS"
done

echo "=== FASE FINAL: STATUS COMPLETO ==="
curl -sf -H "x-trust-token: $TRUST" -H "x-request-id: $(uuidgen)" -H "x-idempotency-key: $(uuidgen)" $BASE/agents | python3 -c "import sys,json; agents=json.load(sys.stdin); [print(f\"  {a['id']} [{a['status']}]\") for a in agents]; print(f'TOTAL: {len(agents)} agentes')"
bash /home/jod_robo/JOD_ROBO/chaos_test.sh

echo "=== COMMIT GITHUB ==="
cd /home/jod_robo/JOD_ROBO && git add CLAUDE.md telegram_bot_patch.py chaos_test.sh predictive_healing.py && git commit -m "fix: tool_calls reais, chaos tests, CLAUDE.md, healing porta corrigida" && git push origin main

