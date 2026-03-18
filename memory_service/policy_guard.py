"""
Barreira formal do memory_service.

Contrato operacional (MEMORY_BOUNDARY):
  1. RetrievalGateway entrega APENAS contexto advisory_only — nunca decisões.
  2. memory_service não governa nenhuma decisão do core (robo_mae/).
  3. policy_guard é a barreira de execução: enforce_advisory() é chamado em
     toda saída do gateway e levanta MemoryGovernanceError se advisory_only
     não for True, impedindo que memória cognitiva seja usada operacionalmente.
"""
from __future__ import annotations

CRITICAL_OPERATIONS: frozenset[str] = frozenset({
    "delete_all_episodic",
    "delete_all_semantic",
    "delete_all_procedural",
    "delete_all_graph",
    "hard_reset",
    "alter_schema",
})


class MemoryGovernanceError(Exception):
    """Levantada quando a barreira advisory é violada ou operação crítica tentada."""


def assert_advisory_only(operation: str) -> None:
    """Impede execução de operações críticas sem aprovação explícita."""
    if operation in CRITICAL_OPERATIONS:
        raise MemoryGovernanceError(
            f"Operação crítica proibida sem aprovação explícita: {operation}"
        )


def wrap_advisory(data: object) -> dict:
    """Envolve dado em envelope advisory_only. Sempre seguido de enforce_advisory()."""
    return {"advisory_only": True, "data": data}


def enforce_advisory(response: dict) -> dict:
    """
    Barreira formal — valida que toda saída do gateway é advisory_only=True.

    Chamado por RetrievalGateway em todos os métodos públicos.
    Se advisory_only não for True, levanta MemoryGovernanceError:
    memória cognitiva não pode ser usada operacionalmente sem aprovação explícita.
    """
    if not response.get("advisory_only"):
        raise MemoryGovernanceError(
            "Saída do memory_service deve ter advisory_only=True — "
            "uso operacional de memória cognitiva não é permitido."
        )
    return response
