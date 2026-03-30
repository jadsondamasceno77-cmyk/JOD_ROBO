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
