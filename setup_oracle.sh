#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# JOD_ROBO — Setup automático para Oracle Cloud ARM (Ubuntu 22.04)
# Uso: curl -sSL https://raw.githubusercontent.com/.../setup_oracle.sh | bash
# Ou:  bash setup_oracle.sh --niche fitness --country BR --instance-id mae-1
# ─────────────────────────────────────────────────────────────────────────────

set -e

# ── Argumentos ───────────────────────────────────────────────────────────────
NICHE="geral"
COUNTRY="BR"
INSTANCE_ID="mae-1"
GROQ_API_KEY=""
CENTRAL_URL=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --niche)        NICHE="$2";        shift 2 ;;
    --country)      COUNTRY="$2";     shift 2 ;;
    --instance-id)  INSTANCE_ID="$2"; shift 2 ;;
    --groq-key)     GROQ_API_KEY="$2"; shift 2 ;;
    --central)      CENTRAL_URL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "╔══════════════════════════════════════════════════════╗"
echo "║  JOD_ROBO — Instalando Robô Mãe: $INSTANCE_ID"
echo "║  Nicho: $NICHE | País: $COUNTRY"
echo "╚══════════════════════════════════════════════════════╝"

PUBLIC_IP=$(curl -s ifconfig.me)
echo "IP público detectado: $PUBLIC_IP"

# ── 1. Atualiza sistema ───────────────────────────────────────────────────────
echo "[1/8] Atualizando sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq git curl wget unzip docker.io docker-compose-plugin \
    python3-pip python3-venv ffmpeg

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# ── 2. Firewall — libera portas necessárias ───────────────────────────────────
echo "[2/8] Configurando firewall..."
sudo iptables -I INPUT -p tcp --dport 5678 -j ACCEPT   # n8n
sudo iptables -I INPUT -p tcp --dport 37779 -j ACCEPT  # ELI API
sudo iptables -I INPUT -p tcp --dport 3001 -j ACCEPT   # Monitor
sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null 2>&1 || true

# Oracle Cloud também bloqueia via VCN Security List
# Lembre de abrir as portas no painel Oracle também

# ── 3. Clona o repositório ────────────────────────────────────────────────────
echo "[3/8] Clonando JOD_ROBO..."
if [ ! -d "/opt/jod_robo" ]; then
    sudo git clone https://github.com/jod-robo/jod_robo.git /opt/jod_robo 2>/dev/null || {
        # Se não tem repo público, copia do local
        sudo mkdir -p /opt/jod_robo
        echo "AVISO: Configure o repositório manualmente em /opt/jod_robo"
    }
fi
sudo chown -R $USER:$USER /opt/jod_robo
cd /opt/jod_robo

# ── 4. Cria arquivo .env ──────────────────────────────────────────────────────
echo "[4/8] Configurando variáveis de ambiente..."
cat > /opt/jod_robo/.env << EOF
# JOD_ROBO — Robô Mãe: $INSTANCE_ID
INSTANCE_ID=$INSTANCE_ID
NICHE=$NICHE
COUNTRY=$COUNTRY
PUBLIC_IP=$PUBLIC_IP

# API Keys
GROQ_API_KEY=$GROQ_API_KEY
JOD_TRUST_MANIFEST=jod_robo_trust_2026_secure

# Database
DB_PASSWORD=jod_secure_$(openssl rand -hex 8)

# n8n
N8N_USER=admin
N8N_PASSWORD=jod_$(openssl rand -hex 6)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 16)

# Workers
MAX_WORKERS=10

# Central Manager (se existir)
CENTRAL_URL=$CENTRAL_URL
EOF

echo "Credenciais salvas em /opt/jod_robo/.env"

# ── 5. Baixa modelos Kokoro (voz premium) ─────────────────────────────────────
echo "[5/8] Baixando modelos de voz Kokoro..."
mkdir -p /opt/jod_robo/models
cd /opt/jod_robo/models
[ ! -f kokoro-v1.0.onnx ] && wget -q --show-progress \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
[ ! -f voices-v1.0.bin ] && wget -q --show-progress \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd /opt/jod_robo

# ── 6. Sobe os containers ─────────────────────────────────────────────────────
echo "[6/8] Subindo containers Docker..."
cd /opt/jod_robo
docker compose --env-file .env up -d

# ── 7. Aguarda serviços subirem ───────────────────────────────────────────────
echo "[7/8] Aguardando serviços..."
sleep 15

N8N_PASS=$(grep N8N_PASSWORD .env | cut -d= -f2)

# Testa ELI API
ELI_STATUS=$(curl -s http://localhost:37779/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null || echo "offline")

# Testa n8n
N8N_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz 2>/dev/null || echo "000")

# ── 8. Registra no manager central ───────────────────────────────────────────
echo "[8/8] Registrando instância..."
if [ -n "$CENTRAL_URL" ]; then
    curl -s -X POST "$CENTRAL_URL/register" \
        -H "Content-Type: application/json" \
        -d "{
            \"instance_id\": \"$INSTANCE_ID\",
            \"ip\": \"$PUBLIC_IP\",
            \"niche\": \"$NICHE\",
            \"country\": \"$COUNTRY\",
            \"eli_url\": \"http://$PUBLIC_IP:37779\",
            \"n8n_url\": \"http://$PUBLIC_IP:5678\"
        }" > /dev/null 2>&1 || true
fi

# ── Resumo ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ROBÔ MÃE INSTALADO COM SUCESSO!                        ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Instância:  $INSTANCE_ID"
echo "║  Nicho:      $NICHE | País: $COUNTRY"
echo "║  IP público: $PUBLIC_IP"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  ELI API:  http://$PUBLIC_IP:37779/health  [$ELI_STATUS]"
echo "║  n8n:      http://$PUBLIC_IP:5678          [$N8N_STATUS]"
echo "║  Monitor:  http://$PUBLIC_IP:3001"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  n8n login: admin / $N8N_PASS"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "LEMBRE: Abra as portas 5678, 37779, 3001 no painel Oracle VCN"
