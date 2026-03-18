"""
Gateway de recuperação — todas as saídas são advisory_only (enforcement via policy_guard).

Contrato:
- Nenhum método deste módulo retorna dados sem passar por enforce_advisory().
- memory_service não governa nenhuma decisão do core (robo_mae/).
- Memória cognitiva sugere; memória operacional decide.
"""
from __future__ import annotations

from .policy_guard import enforce_advisory, wrap_advisory
from .storage import (
    find_node_by_label,
    insert_episodic_event,
    list_episodic_events,
    list_graph_neighbors,
    list_graph_nodes,
    list_procedural_patterns,
    list_semantic_facts,
)


class RetrievalGateway:
    def __init__(self, session_factory):
        self._sf = session_factory

    def query_episodic(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        limit: int = 20,
    ) -> dict:
        return enforce_advisory(wrap_advisory(
            list_episodic_events(self._sf, agent_id=agent_id,
                                 event_type=event_type, limit=limit)
        ))

    def query_semantic(
        self,
        category: str | None = None,
        key: str | None = None,
    ) -> dict:
        return enforce_advisory(wrap_advisory(
            list_semantic_facts(self._sf, category=category, key=key)
        ))

    def query_procedural(self, name: str | None = None) -> dict:
        return enforce_advisory(wrap_advisory(
            list_procedural_patterns(self._sf, name=name)
        ))

    def query_graph(self, node_id: str, relation: str | None = None) -> dict:
        return enforce_advisory(wrap_advisory(
            list_graph_neighbors(self._sf, node_id=node_id, relation=relation)
        ))

    def build_agent_context(self, agent_id: str) -> dict:
        """
        Contexto composto: episodic + semantic + procedural + graph.

        Graph: prioriza neighbors/relations do agente quando existe nó com
        label=agent_id no grafo; usa fallback de nós recentes quando não há
        vínculo específico.
        """
        agent_node_id = find_node_by_label(self._sf, agent_id)
        if agent_node_id:
            graph_data = list_graph_neighbors(self._sf, agent_node_id)
        else:
            graph_data = list_graph_nodes(self._sf, limit=20)

        return enforce_advisory(wrap_advisory({
            "episodic":   list_episodic_events(self._sf, agent_id=agent_id, limit=5),
            "semantic":   list_semantic_facts(self._sf),
            "procedural": list_procedural_patterns(self._sf),
            "graph":      graph_data,
        }))

    def reflect_and_consolidate(self, agent_id: str, intent: str) -> dict:
        """Stub: registra intenção como evento episódico, retorna advisory pending_consolidation."""
        event_id = insert_episodic_event(
            self._sf, agent_id=agent_id,
            event_type="consolidation_intent", summary=intent,
        )
        return enforce_advisory(wrap_advisory(
            {"status": "pending_consolidation", "event_id": event_id}
        ))
