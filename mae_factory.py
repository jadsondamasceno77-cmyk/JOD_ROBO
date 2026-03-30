#!/usr/bin/env python3
"""
Mae Factory — gera e gerencia 100 agentes mãe n8n
Cada mãe = nicho único + país único + voz única + estratégia única
"""
import os
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
CONFIG_FILE = BASE / "maes_100.json"

# ─── 100 Mães — 10 grupos × 10 nichos × múltiplos países ─────────────────────

MAES_100 = [
    # ── GRUPO 1: FITNESS / SAÚDE ─────────────────────────────────────────────
    {"id":"mae-001","niche":"fitness","sub":"musculação e hipertrofia","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_adam","hours":["06:00","12:00","19:00"]},
    {"id":"mae-002","niche":"yoga","sub":"yoga para iniciantes","country":"IN","lang":"hi","region":"ap-mumbai-1","voice":"af_bella","hours":["07:00","13:00","20:00"]},
    {"id":"mae-003","niche":"running","sub":"corrida e maratona","country":"DE","lang":"de","region":"eu-frankfurt-1","voice":"bm_george","hours":["06:30","12:30","19:30"]},
    {"id":"mae-004","niche":"nutricao","sub":"alimentação saudável","country":"MX","lang":"es","region":"mx-queretaro-1","voice":"af_nova","hours":["07:00","13:00","20:00"]},
    {"id":"mae-005","niche":"saude_mental","sub":"ansiedade e bem-estar","country":"CA","lang":"en-CA","region":"ca-toronto-1","voice":"af_sky","hours":["08:00","14:00","21:00"]},
    {"id":"mae-006","niche":"crossfit","sub":"treino funcional","country":"US","lang":"en","region":"us-ashburn-1","voice":"am_michael","hours":["05:30","12:00","18:00"]},
    {"id":"mae-007","niche":"pilates","sub":"pilates e postura","country":"ES","lang":"es","region":"eu-madrid-1","voice":"af_heart","hours":["07:00","13:00","20:00"]},
    {"id":"mae-008","niche":"meditacao","sub":"mindfulness e meditação","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"af_bella","hours":["06:00","12:00","21:00"]},
    {"id":"mae-009","niche":"emagrecimento","sub":"perda de peso saudável","country":"AR","lang":"es","region":"sa-saopaulo-1","voice":"af_nova","hours":["07:00","12:00","20:00"]},
    {"id":"mae-010","niche":"bodybuilding","sub":"fisiculturismo natural","country":"NG","lang":"en","region":"af-johannesburg-1","voice":"am_adam","hours":["06:00","13:00","19:00"]},

    # ── GRUPO 2: NEGÓCIOS / EMPREENDEDORISMO ──────────────────────────────────
    {"id":"mae-011","niche":"empreendedorismo","sub":"startups e inovação","country":"US","lang":"en","region":"us-phoenix-1","voice":"am_michael","hours":["07:00","12:00","18:00"]},
    {"id":"mae-012","niche":"marketing_digital","sub":"tráfego pago e SEO","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_adam","hours":["08:00","13:00","19:00"]},
    {"id":"mae-013","niche":"personal_branding","sub":"reputação do fundador","country":"GB","lang":"en-GB","region":"uk-london-1","voice":"bm_george","hours":["07:30","12:30","19:00"]},
    {"id":"mae-014","niche":"lideranca","sub":"gestão de equipes","country":"DE","lang":"de","region":"eu-frankfurt-1","voice":"bm_george","hours":["07:00","13:00","18:00"]},
    {"id":"mae-015","niche":"produtividade","sub":"gestão de tempo","country":"AU","lang":"en-AU","region":"ap-sydney-1","voice":"am_michael","hours":["07:00","12:00","19:00"]},
    {"id":"mae-016","niche":"financas_pessoais","sub":"investimentos para iniciantes","country":"SG","lang":"en-SG","region":"ap-singapore-1","voice":"am_michael","hours":["07:00","12:00","20:00"]},
    {"id":"mae-017","niche":"investimentos","sub":"bolsa de valores e cripto","country":"KR","lang":"ko","region":"ap-seoul-1","voice":"am_adam","hours":["08:00","13:00","21:00"]},
    {"id":"mae-018","niche":"ecommerce","sub":"loja virtual e dropshipping","country":"ID","lang":"id","region":"ap-jakarta-1","voice":"af_nova","hours":["07:00","13:00","20:00"]},
    {"id":"mae-019","niche":"vendas","sub":"técnicas de vendas e fechamento","country":"CO","lang":"es","region":"sa-saopaulo-1","voice":"am_adam","hours":["08:00","13:00","19:00"]},
    {"id":"mae-020","niche":"negocios_digitais","sub":"renda online e liberdade","country":"PT","lang":"pt-PT","region":"eu-frankfurt-1","voice":"am_michael","hours":["08:00","14:00","20:00"]},

    # ── GRUPO 3: BELEZA / MODA ────────────────────────────────────────────────
    {"id":"mae-021","niche":"skincare","sub":"cuidados naturais com a pele","country":"KR","lang":"ko","region":"ap-seoul-1","voice":"af_bella","hours":["08:00","13:00","20:00"]},
    {"id":"mae-022","niche":"maquiagem","sub":"make para o dia a dia","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_heart","hours":["08:00","13:00","20:00"]},
    {"id":"mae-023","niche":"moda_feminina","sub":"looks e tendências","country":"FR","lang":"fr","region":"eu-paris-1","voice":"af_nova","hours":["09:00","13:00","20:00"]},
    {"id":"mae-024","niche":"cabelos","sub":"cuidados e transformações","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_sky","hours":["08:00","13:00","19:00"]},
    {"id":"mae-025","niche":"unhas","sub":"nail art e designs","country":"US","lang":"en","region":"us-sanjose-1","voice":"af_bella","hours":["09:00","14:00","20:00"]},
    {"id":"mae-026","niche":"moda_sustentavel","sub":"moda consciente e ética","country":"NL","lang":"nl","region":"eu-amsterdam-1","voice":"bf_emma","hours":["08:00","13:00","19:00"]},
    {"id":"mae-027","niche":"streetwear","sub":"moda urbana e sneakers","country":"US","lang":"en","region":"us-ashburn-1","voice":"am_adam","hours":["10:00","15:00","21:00"]},
    {"id":"mae-028","niche":"moda_masculina","sub":"estilo e elegância masculina","country":"IT","lang":"it","region":"eu-frankfurt-1","voice":"bm_george","hours":["08:00","13:00","19:00"]},
    {"id":"mae-029","niche":"beleza_natural","sub":"cosméticos naturais e veganos","country":"AU","lang":"en-AU","region":"ap-sydney-1","voice":"af_heart","hours":["08:00","13:00","20:00"]},
    {"id":"mae-030","niche":"perfumaria","sub":"perfumes e fragrâncias","country":"AE","lang":"ar","region":"me-dubai-1","voice":"af_bella","hours":["09:00","14:00","21:00"]},

    # ── GRUPO 4: GASTRONOMIA / CULINÁRIA ──────────────────────────────────────
    {"id":"mae-031","niche":"receitas","sub":"receitas rápidas do dia a dia","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_nova","hours":["07:00","12:00","19:00"]},
    {"id":"mae-032","niche":"vegano","sub":"culinária vegana e plant-based","country":"DE","lang":"de","region":"eu-frankfurt-1","voice":"af_bella","hours":["08:00","13:00","20:00"]},
    {"id":"mae-033","niche":"confeitaria","sub":"bolos e sobremesas","country":"FR","lang":"fr","region":"eu-paris-1","voice":"af_heart","hours":["09:00","14:00","20:00"]},
    {"id":"mae-034","niche":"churrasco","sub":"churrasqueiro e defumados","country":"AR","lang":"es","region":"sa-saopaulo-1","voice":"am_adam","hours":["11:00","16:00","20:00"]},
    {"id":"mae-035","niche":"comida_saudavel","sub":"meal prep e alimentação limpa","country":"US","lang":"en","region":"us-phoenix-1","voice":"af_sky","hours":["07:00","12:00","18:00"]},
    {"id":"mae-036","niche":"barista","sub":"café especial e latte art","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"af_bella","hours":["07:00","12:00","18:00"]},
    {"id":"mae-037","niche":"comida_de_rua","sub":"street food e gastronomia popular","country":"TH","lang":"th","region":"ap-singapore-1","voice":"af_nova","hours":["10:00","15:00","20:00"]},
    {"id":"mae-038","niche":"drinks","sub":"coquetéis e mixologia","country":"MX","lang":"es","region":"mx-queretaro-1","voice":"am_michael","hours":["16:00","19:00","22:00"]},
    {"id":"mae-039","niche":"paes","sub":"pães artesanais e fermentação","country":"PT","lang":"pt-PT","region":"eu-frankfurt-1","voice":"af_heart","hours":["07:00","12:00","18:00"]},
    {"id":"mae-040","niche":"gastronomia_gourmet","sub":"alta gastronomia acessível","country":"IT","lang":"it","region":"eu-frankfurt-1","voice":"bm_george","hours":["12:00","16:00","20:00"]},

    # ── GRUPO 5: TECNOLOGIA ───────────────────────────────────────────────────
    {"id":"mae-041","niche":"inteligencia_artificial","sub":"IA para o dia a dia","country":"US","lang":"en","region":"us-ashburn-1","voice":"am_michael","hours":["08:00","13:00","19:00"]},
    {"id":"mae-042","niche":"programacao","sub":"dev web e mobile","country":"IN","lang":"hi","region":"ap-mumbai-1","voice":"am_adam","hours":["08:00","14:00","20:00"]},
    {"id":"mae-043","niche":"cyberseguranca","sub":"segurança digital e privacidade","country":"DE","lang":"de","region":"eu-frankfurt-1","voice":"bm_george","hours":["08:00","13:00","19:00"]},
    {"id":"mae-044","niche":"gadgets","sub":"tecnologia e lançamentos","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"am_michael","hours":["09:00","14:00","21:00"]},
    {"id":"mae-045","niche":"games","sub":"gaming e esports","country":"KR","lang":"ko","region":"ap-seoul-1","voice":"am_adam","hours":["14:00","19:00","23:00"]},
    {"id":"mae-046","niche":"automacao","sub":"automação de processos com IA","country":"GB","lang":"en-GB","region":"uk-london-1","voice":"bm_george","hours":["08:00","13:00","18:00"]},
    {"id":"mae-047","niche":"blockchain","sub":"cripto e web3","country":"SG","lang":"en-SG","region":"ap-singapore-1","voice":"am_michael","hours":["09:00","14:00","21:00"]},
    {"id":"mae-048","niche":"saas","sub":"produtos digitais e SaaS","country":"US","lang":"en","region":"us-sanjose-1","voice":"am_adam","hours":["08:00","13:00","18:00"]},
    {"id":"mae-049","niche":"design_ux","sub":"UX/UI e design de produto","country":"NL","lang":"nl","region":"eu-amsterdam-1","voice":"af_nova","hours":["09:00","14:00","19:00"]},
    {"id":"mae-050","niche":"no_code","sub":"ferramentas no-code e automação","country":"AU","lang":"en-AU","region":"ap-sydney-1","voice":"am_michael","hours":["08:00","13:00","19:00"]},

    # ── GRUPO 6: VIAGENS ──────────────────────────────────────────────────────
    {"id":"mae-051","niche":"mochileiro","sub":"viagens com baixo orçamento","country":"AU","lang":"en-AU","region":"ap-sydney-1","voice":"am_adam","hours":["07:00","13:00","20:00"]},
    {"id":"mae-052","niche":"viagem_luxo","sub":"hotéis e experiências premium","country":"AE","lang":"ar","region":"me-dubai-1","voice":"bm_george","hours":["09:00","14:00","21:00"]},
    {"id":"mae-053","niche":"viagem_familia","sub":"destinos para família","country":"US","lang":"en","region":"us-ashburn-1","voice":"af_bella","hours":["08:00","13:00","19:00"]},
    {"id":"mae-054","niche":"nomade_digital","sub":"trabalhe de qualquer lugar","country":"PT","lang":"pt-PT","region":"eu-frankfurt-1","voice":"am_michael","hours":["09:00","14:00","20:00"]},
    {"id":"mae-055","niche":"fotografia_viagem","sub":"fotografia e dicas de destinos","country":"FR","lang":"fr","region":"eu-paris-1","voice":"af_nova","hours":["08:00","14:00","20:00"]},
    {"id":"mae-056","niche":"van_life","sub":"vida em van e liberdade","country":"US","lang":"en","region":"us-phoenix-1","voice":"am_adam","hours":["08:00","14:00","20:00"]},
    {"id":"mae-057","niche":"aventura","sub":"trilhas e esportes radicais","country":"NZ","lang":"en","region":"ap-sydney-1","voice":"am_michael","hours":["07:00","12:00","19:00"]},
    {"id":"mae-058","niche":"viagem_solo","sub":"viajar sozinho com segurança","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"af_sky","hours":["08:00","14:00","21:00"]},
    {"id":"mae-059","niche":"camping","sub":"vida ao ar livre e camping","country":"CA","lang":"en-CA","region":"ca-toronto-1","voice":"am_adam","hours":["07:00","12:00","19:00"]},
    {"id":"mae-060","niche":"cruzeiros","sub":"cruzeiros e turismo marítimo","country":"IT","lang":"it","region":"eu-frankfurt-1","voice":"af_bella","hours":["09:00","14:00","20:00"]},

    # ── GRUPO 7: EDUCAÇÃO / DESENVOLVIMENTO ───────────────────────────────────
    {"id":"mae-061","niche":"ingles","sub":"aprender inglês rápido","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_michael","hours":["07:00","12:00","19:00"]},
    {"id":"mae-062","niche":"cursos_online","sub":"educação digital e EAD","country":"IN","lang":"hi","region":"ap-mumbai-1","voice":"af_nova","hours":["08:00","14:00","20:00"]},
    {"id":"mae-063","niche":"desenvolvimento_pessoal","sub":"crescimento e mindset","country":"US","lang":"en","region":"us-ashburn-1","voice":"am_michael","hours":["07:00","12:00","18:00"]},
    {"id":"mae-064","niche":"carreira","sub":"mercado de trabalho e LinkedIn","country":"GB","lang":"en-GB","region":"uk-london-1","voice":"bm_george","hours":["07:00","12:00","18:00"]},
    {"id":"mae-065","niche":"parentalidade","sub":"criação de filhos e família","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_heart","hours":["08:00","14:00","21:00"]},
    {"id":"mae-066","niche":"psicologia","sub":"saúde emocional e terapia","country":"CA","lang":"en-CA","region":"ca-montreal-1","voice":"af_sky","hours":["09:00","14:00","21:00"]},
    {"id":"mae-067","niche":"coach","sub":"coaching executivo e de vida","country":"DE","lang":"de","region":"eu-frankfurt-1","voice":"bm_george","hours":["08:00","13:00","19:00"]},
    {"id":"mae-068","niche":"estudo","sub":"técnicas de aprendizado","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"am_michael","hours":["07:00","13:00","21:00"]},
    {"id":"mae-069","niche":"idiomas","sub":"poliglotismo e aprendizado de línguas","country":"FR","lang":"fr","region":"eu-paris-1","voice":"af_bella","hours":["08:00","14:00","20:00"]},
    {"id":"mae-070","niche":"filosofia","sub":"filosofia aplicada ao cotidiano","country":"GR","lang":"el","region":"eu-frankfurt-1","voice":"bm_george","hours":["09:00","15:00","21:00"]},

    # ── GRUPO 8: ARTES / CRIATIVIDADE ─────────────────────────────────────────
    {"id":"mae-071","niche":"fotografia","sub":"fotografia e edição","country":"US","lang":"en","region":"us-ashburn-1","voice":"af_nova","hours":["09:00","14:00","20:00"]},
    {"id":"mae-072","niche":"design_grafico","sub":"identidade visual e branding","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_heart","hours":["09:00","14:00","20:00"]},
    {"id":"mae-073","niche":"ilustracao","sub":"ilustração digital e concept art","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"af_bella","hours":["10:00","15:00","21:00"]},
    {"id":"mae-074","niche":"musica","sub":"produção musical e beats","country":"US","lang":"en","region":"us-phoenix-1","voice":"am_adam","hours":["12:00","17:00","22:00"]},
    {"id":"mae-075","niche":"escrita","sub":"copywriting e criação de conteúdo","country":"GB","lang":"en-GB","region":"uk-london-1","voice":"bf_emma","hours":["08:00","13:00","19:00"]},
    {"id":"mae-076","niche":"video","sub":"edição de vídeo e YouTube","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_michael","hours":["10:00","15:00","21:00"]},
    {"id":"mae-077","niche":"arquitetura","sub":"arquitetura e design de interiores","country":"IT","lang":"it","region":"eu-frankfurt-1","voice":"bm_george","hours":["09:00","14:00","20:00"]},
    {"id":"mae-078","niche":"artesanato","sub":"DIY e trabalhos manuais","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_heart","hours":["09:00","14:00","20:00"]},
    {"id":"mae-079","niche":"animacao","sub":"animação 2D e 3D","country":"US","lang":"en","region":"us-sanjose-1","voice":"am_adam","hours":["10:00","15:00","21:00"]},
    {"id":"mae-080","niche":"tatuagem","sub":"tattoo e body art","country":"US","lang":"en","region":"us-ashburn-1","voice":"am_adam","hours":["11:00","16:00","22:00"]},

    # ── GRUPO 9: LIFESTYLE / ESTILO DE VIDA ───────────────────────────────────
    {"id":"mae-081","niche":"minimalismo","sub":"vida simples e essencial","country":"JP","lang":"ja","region":"ap-tokyo-1","voice":"af_sky","hours":["07:00","12:00","20:00"]},
    {"id":"mae-082","niche":"sustentabilidade","sub":"vida sustentável e ecológica","country":"SE","lang":"sv","region":"eu-amsterdam-1","voice":"bf_emma","hours":["08:00","13:00","19:00"]},
    {"id":"mae-083","niche":"decoracao","sub":"decoração e home decor","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_nova","hours":["09:00","14:00","20:00"]},
    {"id":"mae-084","niche":"jardinagem","sub":"plantas e horta em casa","country":"NL","lang":"nl","region":"eu-amsterdam-1","voice":"af_bella","hours":["08:00","13:00","19:00"]},
    {"id":"mae-085","niche":"pets","sub":"cães e gatos e vida com pets","country":"US","lang":"en","region":"us-ashburn-1","voice":"af_heart","hours":["08:00","14:00","20:00"]},
    {"id":"mae-086","niche":"luxo","sub":"lifestyle de luxo e alto padrão","country":"AE","lang":"ar","region":"me-dubai-1","voice":"bm_george","hours":["10:00","15:00","21:00"]},
    {"id":"mae-087","niche":"relacionamentos","sub":"relacionamentos e comunicação","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"af_sky","hours":["09:00","14:00","21:00"]},
    {"id":"mae-088","niche":"autoconhecimento","sub":"espiritualidade e propósito","country":"IN","lang":"hi","region":"ap-mumbai-1","voice":"af_bella","hours":["07:00","12:00","21:00"]},
    {"id":"mae-089","niche":"van_life_br","sub":"vida simples e viagem de carro","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_adam","hours":["08:00","14:00","20:00"]},
    {"id":"mae-090","niche":"biohacking","sub":"otimização do corpo e mente","country":"US","lang":"en","region":"us-sanjose-1","voice":"am_michael","hours":["06:00","12:00","18:00"]},

    # ── GRUPO 10: ESPORTES ────────────────────────────────────────────────────
    {"id":"mae-091","niche":"futebol","sub":"análise e bastidores do futebol","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_adam","hours":["12:00","18:00","22:00"]},
    {"id":"mae-092","niche":"basquete","sub":"NBA e basquete mundial","country":"US","lang":"en","region":"us-ashburn-1","voice":"am_michael","hours":["12:00","18:00","23:00"]},
    {"id":"mae-093","niche":"tenis","sub":"tênis e esportes de raquete","country":"GB","lang":"en-GB","region":"uk-london-1","voice":"bm_george","hours":["09:00","14:00","19:00"]},
    {"id":"mae-094","niche":"natacao","sub":"natação e esportes aquáticos","country":"AU","lang":"en-AU","region":"ap-sydney-1","voice":"am_adam","hours":["06:00","12:00","19:00"]},
    {"id":"mae-095","niche":"ciclismo","sub":"ciclismo urbano e mountain bike","country":"NL","lang":"nl","region":"eu-amsterdam-1","voice":"am_michael","hours":["07:00","12:00","18:00"]},
    {"id":"mae-096","niche":"artes_marciais","sub":"MMA e artes marciais","country":"BR","lang":"pt-BR","region":"sa-saopaulo-1","voice":"am_adam","hours":["07:00","13:00","19:00"]},
    {"id":"mae-097","niche":"esports","sub":"esports e streaming de games","country":"KR","lang":"ko","region":"ap-seoul-1","voice":"am_michael","hours":["14:00","20:00","23:00"]},
    {"id":"mae-098","niche":"golfe","sub":"golfe e country club lifestyle","country":"US","lang":"en","region":"us-phoenix-1","voice":"bm_george","hours":["08:00","13:00","18:00"]},
    {"id":"mae-099","niche":"skate","sub":"skateboard e cultura urbana","country":"US","lang":"en","region":"us-sanjose-1","voice":"am_adam","hours":["12:00","17:00","22:00"]},
    {"id":"mae-100","niche":"atletismo","sub":"corrida de alta performance","country":"KE","lang":"sw","region":"af-johannesburg-1","voice":"am_michael","hours":["05:30","12:00","18:00"]},
]

def generate_configs():
    """Gera arquivo JSON com todos os 100 agentes."""
    config = {
        "total": len(MAES_100),
        "generated_at": datetime.now().isoformat(),
        "maes": MAES_100
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"✅ {len(MAES_100)} agentes mãe gerados em {CONFIG_FILE}")
    return config

def generate_env(mae: dict) -> str:
    """Gera arquivo .env para uma mãe específica."""
    return f"""# JOD_ROBO — Robô Mãe: {mae['id']}
INSTANCE_ID={mae['id']}
NICHE={mae['niche']}
SUB_NICHE={mae['sub']}
COUNTRY={mae['country']}
LANG={mae['lang']}
ORACLE_REGION={mae['region']}
KOKORO_VOICE={mae['voice']}
POST_HOURS={','.join(mae['hours'])}
GROQ_API_KEY=$GROQ_API_KEY
JOD_TRUST_MANIFEST=jod_robo_trust_2026_secure
DB_PASSWORD=jod_{mae['id']}_secure
N8N_USER=admin
N8N_PASSWORD=jod_{mae['id']}_n8n
N8N_ENCRYPTION_KEY=key_{mae['id']}_encrypt
MAX_WORKERS=10
PUBLIC_IP=PENDING
"""

def generate_all_envs():
    """Gera .env para todos os 100 agentes."""
    envs_dir = BASE / "maes_envs"
    envs_dir.mkdir(exist_ok=True)
    for mae in MAES_100:
        env_path = envs_dir / f"{mae['id']}.env"
        env_path.write_text(generate_env(mae))
    print(f"✅ {len(MAES_100)} arquivos .env gerados em {envs_dir}/")

def generate_deploy_commands():
    """Gera comandos de deploy para todos os 100 agentes."""
    commands = []
    for mae in MAES_100:
        cmd = (
            f"bash setup_oracle.sh "
            f"--instance-id {mae['id']} "
            f"--niche {mae['niche']} "
            f"--country {mae['country']} "
            f"--groq-key $GROQ_API_KEY"
        )
        commands.append({"id": mae["id"], "region": mae["region"], "command": cmd})

    deploy_file = BASE / "deploy_commands.json"
    deploy_file.write_text(json.dumps(commands, indent=2, ensure_ascii=False))
    print(f"✅ {len(commands)} comandos de deploy gerados em {deploy_file}")
    return commands

def status_dashboard():
    """Mostra status resumido dos 100 agentes."""
    config = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else generate_configs()
    maes = config["maes"]

    countries = {}
    niches_groups = {}
    for mae in maes:
        countries[mae["country"]] = countries.get(mae["country"], 0) + 1
        group = mae["id"].split("-")[1][0]  # primeiro dígito do número
        niches_groups[group] = niches_groups.get(group, 0) + 1

    print("\n" + "="*60)
    print(f"  JOD_ROBO — {len(maes)} ROBÔS MÃE CONFIGURADOS")
    print("="*60)
    print(f"\n  PAÍSES ({len(countries)} países):")
    for country, count in sorted(countries.items(), key=lambda x: -x[1]):
        print(f"    {country}: {count} mães")
    print(f"\n  GRUPOS:")
    groups = ["FITNESS","NEGÓCIOS","BELEZA","GASTRONOMIA","TECH","VIAGENS","EDUCAÇÃO","ARTES","LIFESTYLE","ESPORTES"]
    for i, g in enumerate(groups, 1):
        print(f"    Grupo {i} — {g}: 10 mães")
    print("\n" + "="*60)

if __name__ == "__main__":
    print("🏭 JOD_ROBO Mae Factory — Gerando 100 agentes...\n")
    generate_configs()
    generate_all_envs()
    generate_deploy_commands()
    status_dashboard()
    print("\n✅ 100 robôs mãe prontos para deploy!")
    print("   Próximo passo: criar contas Oracle e rodar setup_oracle.sh")
