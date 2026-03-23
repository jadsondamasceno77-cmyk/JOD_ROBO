import os
import psycopg2
import sys

# O Arquiteto de IA foca na gestão de infraestrutura de dados [2, 5]
DB_URL = os.getenv("DATABASE_URL")

def inicializar_banco():
    try:
        # A Propriedade da IA exige conexões validadas [6]
        print(f"[*] Tentando conectar ao chassi de dados: {DB_URL.split('@')[-1] if DB_URL else 'URL VAZIA'}")
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # Ativa o pgvector para busca semântica (Padrão RAG 2026) [1, 5]
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Cria a estrutura para o Style DNA dos 50 perfis [3]
        cur.execute("""
            CREATE TABLE IF NOT EXISTS perfis_dna (
                id SERIAL PRIMARY KEY,
                perfil_id INTEGER UNIQUE,
                tom_de_voz TEXT,
                embedding vector(1536),
                status TEXT
            );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("\n[✔] SUCESSO: Memória Semântica (pgvector) ativa no projeto 'infans'.")
    except Exception as e:
        print(f"\n[✘] FALHA NA GOVERNANÇA: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if not DB_URL or "db.[ID]" in DB_URL:
        print("\n[!] ERRO: Você ainda está usando a URL de exemplo!")
    else:
        inicializar_banco()
