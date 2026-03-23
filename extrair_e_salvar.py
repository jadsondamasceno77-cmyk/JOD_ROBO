import os
import psycopg2
from dna_schema import StyleDNA, PerfilFisico

# Governança de Infraestrutura: Padrão Enterprise [2, 4]
DB_URL = os.getenv("DATABASE_URL")

def orquestrar_agentes():
    # Distribuição estratégica de Magnitude para os 50 perfis
    distribuicao = (
        ['portugues_br'] * 20 + 
        ['ingles'] * 15 + 
        ['espanhol'] * 10 + 
        ['frances'] * 5
    )
    
    perfis_para_salvar = []
    for i, lingua in enumerate(distribuicao, 1):
        # Cada perfil é poliglota, mas tem uma 'língua mãe' para o mercado alvo [2]
        perfil = {
            "perfil_id": i,
            "nome_artistico": f"Infans_Global_{i}",
            "lingua_mae": lingua,
            "fisico": {
                "etnia": "Brasileira/Misc", 
                "cor_cabelo": "Variado", 
                "estilo_vestimenta": "Premium/Elegante", 
                "caracteristica_marcante": "Carisma Brasileiro"
            },
            "tom_de_voz": f"Poliglota nato, focado no mercado {lingua}",
            "status": "PRONTO_PARA_EXPORTACAO_ROI"
        }
        perfis_para_salvar.append(perfil)

    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        print(f"[*] Agentes iniciando persistência de {len(perfis_para_salvar)} perfis no pgvector...")
        
        for p_data in perfis_para_salvar:
            # Validação CSDD via Pydantic [1, 3]
            p = StyleDNA(**p_data)
            
            cur.execute("""
                INSERT INTO perfis_dna (perfil_id, tom_de_voz, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (perfil_id) DO UPDATE 
                SET tom_de_voz = EXCLUDED.tom_de_voz, status = EXCLUDED.status;
            """, (p.perfil_id, p.tom_de_voz, p.status))
            
        conn.commit()
        cur.close()
        conn.close()
        print("\n[✔] SUCESSO: 50 Perfis Poliglotas ativos no Chassi de Dados.")
        print("[!] Divulgação Internacional: Liberada para mercados de alta valorização.")
    except Exception as e:
        print(f"\n[✘] FALHA NA GOVERNANÇA (Retry-with-Feedback necessário): {e}")

if __name__ == '__main__':
    orquestrar_agentes()
