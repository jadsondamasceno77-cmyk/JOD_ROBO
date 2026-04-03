#!/usr/bin/env python3
"""
X-Mom Demo Client — gera 3 posts de exemplo ao vivo para reunião de vendas.

Uso:
    python3 demo_client.py "Nome do Cliente" "nicho do cliente"

Exemplo:
    python3 demo_client.py "ClienteTeste" "teste"
    python3 demo_client.py "Barbearia do João" "barbearia masculina"

Salva resultado em /home/jod_robo/outputs/demo_CLIENTE.md
"""
import sys, json, re, asyncio, httpx
from datetime import datetime
from pathlib import Path

API_URL   = "http://localhost:37779/chat"
TOKEN     = "jod_robo_trust_2026_secure"
OUT_DIR   = Path("/home/jod_robo/outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 3 prompts fixos adaptados ao nicho do cliente
DEMO_PROMPTS = [
    "crie um post para instagram de {nicho} com foco em engajamento e hashtags relevantes",
    "escreva uma copy curta de vendas para {nicho} focada em transformação e resultado",
    "crie uma legenda para stories do instagram de {nicho} com call-to-action direto",
]


async def chat(message: str, session_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            API_URL,
            headers={"Content-Type": "application/json", "x-jod-token": TOKEN},
            json={"message": message, "session_id": session_id},
        )
        r.raise_for_status()
        return r.json()


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").upper()


async def run_demo(cliente: str, nicho: str):
    slug    = _slug(cliente)
    session = f"demo-{slug[:8]}-{datetime.now().strftime('%H%M%S')}"
    results = []

    print(f"\n{'='*60}")
    print(f"  X-Mom Demo — {cliente}")
    print(f"  Nicho: {nicho}")
    print(f"  Sessão: {session}")
    print(f"{'='*60}\n")

    for i, tpl in enumerate(DEMO_PROMPTS, 1):
        msg = tpl.format(nicho=nicho)
        print(f"[{i}/3] Gerando: {msg[:65]}...")

        try:
            resp   = await chat(msg, session)
            squad  = resp.get("squad", "?")
            chief  = resp.get("chief", "?")
            text   = resp.get("response", "")
            results.append({"prompt": msg, "squad": squad, "chief": chief, "response": text})

            print(f"      Squad: {squad} → {chief}")
            print(f"\n      {'─'*52}")
            for line in text.split("\n")[:8]:
                print(f"      {line}")
            if text.count("\n") > 7:
                print("      [... resposta completa no arquivo ...]")
            print(f"      {'─'*52}\n")

        except Exception as e:
            print(f"      ⚠ Erro: {e}\n")
            results.append({"prompt": msg, "squad": "erro", "chief": "erro", "response": str(e)})

    # Monta e salva arquivo
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"demo_{slug}.md"
    out_path = OUT_DIR / filename

    lines = [
        f"# Demo X-Mom — {cliente}",
        f"**Nicho:** {nicho}",
        f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"**Sessão:** {session}",
        "",
        "---",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines += [
            f"## Post {i} — {r['prompt'][:60]}",
            f"*Squad: `{r['squad']}` → Chief: `{r['chief']}`*",
            "",
            r["response"],
            "",
            "---",
            "",
        ]
    lines += [
        "## Próximos passos",
        f"- Acesse a demo ao vivo: http://localhost:37779/demo",
        f"- WhatsApp: https://wa.me/5598XXXXXXXX?text=Demo+{slug}",
        "",
        f"*Gerado por X-Mom v5.0 — {datetime.now().isoformat()}*",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"{'='*60}")
    print(f"  ✅ Arquivo salvo: {out_path}")
    print(f"  Posts gerados: {len([r for r in results if r['squad'] != 'erro'])}/3")
    print(f"{'='*60}\n")

    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 demo_client.py \"Nome do Cliente\" \"nicho\"")
        sys.exit(1)

    cliente = sys.argv[1]
    nicho   = sys.argv[2]
    asyncio.run(run_demo(cliente, nicho))
