from typing import Optional

import httpx
from sqlalchemy import text


class AgentRegistry:
    def __init__(
        self,
        session_factory,
        http_client: httpx.AsyncClient,
        base_url: str,
        headers: dict,
    ):
        self._sf   = session_factory
        self._http = http_client
        self._base = base_url
        self._hdrs = headers

    def get_agent_state(self, agent_id: str) -> Optional[dict]:
        """Lê status e template_name da tabela agents. Retorna None se não existe."""
        with self._sf() as s:
            row = s.execute(
                text("SELECT id, status, template_name FROM agents WHERE id = :aid"),
                {"aid": agent_id},
            ).fetchone()
        return dict(row._mapping) if row else None

    async def ensure_active_finalizer(self, agent_id: str) -> None:
        await self._ensure_active(agent_id, "finalizer")

    async def ensure_active_guardian(self, agent_id: str) -> None:
        await self._ensure_active(agent_id, "guardian")

    async def _ensure_active(self, agent_id: str, kind: str) -> None:
        """
        Garante que o agente está em status 'active'.
        Fluxo:
          1. Ler estado via DB (tabela agents) — única fonte de verdade de estado.
          2. Se draft → tentar validate (200 ou 409 — ambos aceitáveis; re-ler DB).
          3. Se ainda não active → tentar activate (200 ou 409 — ambos aceitáveis).
          4. Re-ler DB — verificação final autoritativa.
          5. Falhar com RuntimeError se estado final != 'active'.
        """
        state = self.get_agent_state(agent_id)
        if state is None:
            raise RuntimeError(f"agente {agent_id} não encontrado no DB")

        # Passo 2: validate se draft
        if state["status"] == "draft":
            r = await self._http.post(
                f"{self._base}/agents/{agent_id}/{kind}/validate",
                headers=self._hdrs,
            )
            if r.status_code not in (200, 409):
                raise RuntimeError(
                    f"validate falhou para {agent_id}: {r.status_code} {r.text}"
                )
            state = self.get_agent_state(agent_id)

        # Passo 3: activate se não active
        if state["status"] != "active":
            r = await self._http.post(
                f"{self._base}/agents/{agent_id}/{kind}/activate",
                headers=self._hdrs,
            )
            if r.status_code not in (200, 409):
                raise RuntimeError(
                    f"activate falhou para {agent_id}: {r.status_code} {r.text}"
                )

        # Passo 4: verificação final — DB é autoritativo, não o HTTP response
        state = self.get_agent_state(agent_id)
        if state["status"] != "active":
            raise RuntimeError(
                f"ensure_active falhou para {agent_id}: "
                f"estado final = {state['status']}"
            )
