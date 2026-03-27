#!/usr/bin/env python3
import asyncio, sqlite3, os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

SQLITE_PATH  = os.getenv("DB_PATH", str(Path(__file__).resolve().parent / "jod_robo.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERRO: DATABASE_URL nao definida.")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

async def migrate():
    import asyncpg
    print(f"[1/4] Lendo SQLite: {SQLITE_PATH}")
    conn = sqlite3.connect(SQLITE_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(agents)")
    columns = [col[1] for col in c.fetchall()]
    print(f"      Colunas: {columns}")
    c.execute("SELECT * FROM agents ORDER BY squad,tier,name")
    rows = c.fetchall()
    conn.close()
    print(f"      {len(rows)} agentes encontrados.")
    if not rows:
        print("ERRO: nenhum agente no SQLite.")
        sys.exit(1)

    print(f"[2/4] Conectando PostgreSQL...")
    pg = await asyncpg.connect(DATABASE_URL)
    print(f"      Conectado.")

    print(f"[3/4] Criando schema...")
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL,
            squad TEXT NOT NULL, role TEXT, tier INTEGER DEFAULT 0,
            description TEXT, capabilities TEXT, persona TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW())""")
    await pg.execute("CREATE INDEX IF NOT EXISTS idx_agents_squad ON agents(squad)")
    await pg.execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
    print(f"      Schema OK.")

    col_map = {col: idx for idx, col in enumerate(columns)}
    def g(row, col, default=None):
        idx = col_map.get(col)
        return row[idx] if idx is not None and idx < len(row) else default

    print(f"[4/4] Migrando agentes...")
    ok = skip = errors = 0
    for row in rows:
        name = g(row,"name",""); squad = g(row,"squad","")
        if not name or not squad:
            skip += 1; continue
        try:
            await pg.execute("""
                INSERT INTO agents (name,squad,role,tier,description,capabilities,persona)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (name) DO UPDATE SET
                squad=EXCLUDED.squad, role=EXCLUDED.role, tier=EXCLUDED.tier,
                description=EXCLUDED.description, capabilities=EXCLUDED.capabilities,
                persona=EXCLUDED.persona, updated_at=NOW()""",
                name, squad, g(row,"role",""), g(row,"tier",0) or 0,
                g(row,"description",""), g(row,"capabilities",""), g(row,"persona",""))
            ok += 1
        except Exception as e:
            print(f"      ERRO {name}: {e}"); errors += 1
    await pg.close()
    print(f"\n{'='*50}")
    print(f"  Migrados : {ok}")
    print(f"  Ignorados: {skip}")
    print(f"  Erros    : {errors}")
    print(f"{'='*50}")
    if ok > 0:
        print(f"\nPostgreSQL pronto com {ok} agentes.")

asyncio.run(migrate())
