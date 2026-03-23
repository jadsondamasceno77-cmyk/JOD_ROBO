from pydantic import BaseModel, Field
from typing import List

class PerfilFisico(BaseModel):
    etnia: str
    cor_cabelo: str
    estilo_vestimenta: str
    caracteristica_marcante: str

class StyleDNA(BaseModel):
    perfil_id: int
    nome_artistico: str
    fisico: PerfilFisico
    tom_de_voz: str = Field(..., description="Personalidade de escrita")
    status: str = "ESTRUTURADO_INFANS"
