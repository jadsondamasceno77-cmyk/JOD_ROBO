#!/usr/bin/env bash
# init_session.sh — X-Mom v5.0 session bootstrapper
# Uso: bash /home/jod_robo/XMOM_V5/init_session.sh
# Ou via alias: xmom

XMOM_DIR="/home/jod_robo/XMOM_V5"
OUTPUTS_DIR="/home/jod_robo/outputs"
CONTEXT="$XMOM_DIR/CONTEXT.md"

# ── cores ────────────────────────────────────────────────────────────────────
G='\033[0;32m'   # verde
B='\033[1;34m'   # azul bold
Y='\033[1;33m'   # amarelo
R='\033[0;31m'   # vermelho
W='\033[1;37m'   # branco bold
D='\033[2;37m'   # cinza dim
N='\033[0m'      # reset
BOLD='\033[1m'

hr() { printf "${D}%0.s─${N}" $(seq 1 72); echo; }

# ── header ───────────────────────────────────────────────────────────────────
clear
hr
printf "${G}${BOLD}  ⚡ X-Mom v5.0${N}  ${D}|${N}  ${W}Session Bootstrap${N}  ${D}|${N}  $(date '+%Y-%m-%d %H:%M:%S')\n"
hr

# ── CONTEXT.md ───────────────────────────────────────────────────────────────
printf "\n${B}${BOLD}▸ CONTEXT${N}\n"
if [[ -f "$CONTEXT" ]]; then
  # Extrai seções chave do CONTEXT.md (sem blocos de código longos)
  awk '
    /^## Estado dos Serviços/,/^---/ { print }
    /^## GAPs/,/^---/ { print }
    /^## Banco de Dados/,/^---/ { print }
  ' "$CONTEXT" | grep -v "^---$" | while IFS= read -r line; do
    if [[ "$line" =~ ^## ]]; then
      printf "  ${W}${BOLD}${line}${N}\n"
    elif [[ "$line" =~ ✅ ]]; then
      printf "  ${G}${line}${N}\n"
    elif [[ "$line" =~ ❌ ]]; then
      printf "  ${R}${line}${N}\n"
    elif [[ -n "$line" ]]; then
      printf "  ${D}${line}${N}\n"
    fi
  done
else
  printf "  ${Y}CONTEXT.md não encontrado — rode update_context.sh${N}\n"
fi

# ── serviços systemd ─────────────────────────────────────────────────────────
printf "\n${B}${BOLD}▸ SERVIÇOS${N}\n"
SERVICES=(
  "jod-robo-mae:robo-mae API:37779"
  "jod-factory:Factory:37777"
  "n8n:n8n Workflows:5678"
  "jod-n8n-agent:N8N Agent API:37780"
  "jod-telegram:Telegram Bot:-"
  "jod-health:Health Monitor:-"
  "jod-viewer:Viewer:-"
)
for entry in "${SERVICES[@]}"; do
  svc="${entry%%:*}"
  rest="${entry#*:}"
  label="${rest%%:*}"
  port="${rest##*:}"
  status=$(systemctl is-active "$svc" 2>/dev/null)
  if [[ "$status" == "active" ]]; then
    icon="${G}●${N}"
    col="${G}"
  else
    icon="${R}●${N}"
    col="${R}"
  fi
  if [[ "$port" != "-" ]]; then
    printf "  ${icon} ${col}%-22s${N} ${D}:${port}${N}\n" "$label"
  else
    printf "  ${icon} ${col}%s${N}\n" "$label"
  fi
done

# health check rápido
HEALTH=$(curl -s --max-time 2 http://localhost:37779/health 2>/dev/null)
if [[ -n "$HEALTH" ]]; then
  SQUADS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('squads','?'))" 2>/dev/null)
  AGENTS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agentes','?'))" 2>/dev/null)
  printf "\n  ${D}health → ${G}${SQUADS} squads${D} · ${G}${AGENTS} agentes${N}\n"
fi

# ── últimos outputs ───────────────────────────────────────────────────────────
printf "\n${B}${BOLD}▸ ÚLTIMOS OUTPUTS${N}  ${D}(${OUTPUTS_DIR})${N}\n"
if [[ -d "$OUTPUTS_DIR" ]] && compgen -G "$OUTPUTS_DIR/*.md" > /dev/null 2>&1; then
  ls -t "$OUTPUTS_DIR"/*.md 2>/dev/null | head -3 | while read -r f; do
    fname=$(basename "$f")
    fsize=$(wc -c < "$f" 2>/dev/null | tr -d ' ')
    fdate=$(stat -c '%y' "$f" 2>/dev/null | cut -c1-16)
    printf "  ${G}%-40s${N} ${D}%s  %s bytes${N}\n" "$fname" "$fdate" "$fsize"
    # preview da primeira linha não-vazia
    preview=$(grep -m1 -v '^#\|^---\|^$' "$f" 2>/dev/null | cut -c1-60)
    [[ -n "$preview" ]] && printf "  ${D}  └─ %s…${N}\n" "$preview"
  done
else
  printf "  ${D}Nenhum output encontrado${N}\n"
fi

# ── últimos commits ───────────────────────────────────────────────────────────
printf "\n${B}${BOLD}▸ GIT LOG${N}\n"
GIT_OUT=$(cd "$XMOM_DIR" && git log --oneline --color=never -3 2>/dev/null)
if [[ -n "$GIT_OUT" ]]; then
  while IFS= read -r line; do
    hash="${line%% *}"
    msg="${line#* }"
    printf "  ${Y}%s${N}  ${D}%s${N}\n" "$hash" "$msg"
  done <<< "$GIT_OUT"
else
  printf "  ${D}(repositório sem commits ou não inicializado)${N}\n"
fi

# ── pending tasks no bus ──────────────────────────────────────────────────────
PENDING=$(python3 -c "
import sys; sys.path.insert(0,'$XMOM_DIR')
import xmom_bus; print(xmom_bus.pending_count())
" 2>/dev/null)
if [[ -n "$PENDING" && "$PENDING" != "0" ]]; then
  printf "\n${Y}${BOLD}▸ ATENÇÃO: $PENDING tarefa(s) pendente(s) no bus (xmom_events)${N}\n"
fi

# ── rodapé ───────────────────────────────────────────────────────────────────
printf "\n"
hr
printf "${G}${BOLD}  X-Mom pronta. Aguardando comando do operador.${N}\n"
hr
printf "\n"
