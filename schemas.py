from pydantic import BaseModel, Field
from typing import List

class PerfilStyleDNA(BaseModel):
    perfil_id: int
    tom_de_voz: str = Field(..., description="Estilo de escrita do perfil")
    status: str = "ESTRUTURADO_INFANS"

class ResultadoAgente(BaseModel):
    agente_id: int
    perfis: List[PerfilStyleDNA]
