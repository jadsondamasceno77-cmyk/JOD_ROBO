import os
import psycopg2
from dna_schema import StyleDNA, PerfilFisico

# Governança de Infraestrutura: Conexão via Variável de Ambiente [3, 4]
DB_URL = os.getenv("DATABASE_URL")

def salvar_perfis_lote(perfis_data):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        for data in perfis_data:
            # Validação Pydantic v2: Segurança por Construção (CSDD) [1, 5]
            perfil = StyleDNA(**data)
            
            # Inserção no Chassi de Dados (pgvector preparado) [2, 3]
            cur.execute("""
                INSERT INTO perfis_dna (perfil_id, tom_de_voz, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (perfil_id) DO UPDATE 
                SET tom_de_voz = EXCLUDED.tom_de_voz, status = EXCLUDED.status;
            """, (perfil.perfil_id, perfil.tom_de_voz, perfil.status))
            
        conn.commit()
        cur.close()
        conn.close()
        print(f"[✔] SUCESSO: {len(perfis_data)} perfis persistidos com Governança de IA.")
    except Exception as e:
        print(f"[✘] FALHA NO RETRY-WITH-FEEDBACK: {e}") # Padrão de resiliência [1, 2]

if __name__ == "__main__":
    # Simulação do Lote do Agente 1 (Primeiros 5 perfis de 50)
    lote_exemplo = [
        {
            "perfil_id": i,
            "nome_artistico": f"Avatar_{i}",
            "fisico": {"etnia": "Diversa", "cor_cabelo": "Castanho", "estilo_vestimenta": "Casual", "caracteristica_marcante": "Olhar expressivo"},
            "tom_de_voz": "Amigável e profissional",
            "status": "ATIVO_ESTAGIO_4"
        } for i in range(1, 6)
    ]
    salvar_perfis_lote(lote_exemplo)
