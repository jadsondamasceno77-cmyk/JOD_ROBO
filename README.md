# JOD_ROBO v3.0 — Assistente Autônomo 🤖

Sistema multi-agente autônomo controlado por linguagem natural.
Criado por Jadson Damasceno.

## O Que Faz

- Cria agentes de código via LLM (Groq/Ollama)
- Aprende com cada execução (.jod_memory.json)
- Valida segurança antes de escrever qualquer arquivo
- Versiona automaticamente no Git
- Roda autônomo com --loop

## Instalação
```bash
pip3 install tenacity pydantic pytest
export GROQ_API_KEY="sua-chave-aqui"
```

## Uso
```bash
# Com confirmação (recomendado)
python3 jod_brain_main.py "crie agente de backup"

# Sem confirmação
python3 jod_brain_main.py "crie agente X" --apply

# Autônomo a cada 5 minutos
python3 jod_brain_main.py --loop

# Autônomo com intervalo customizado
python3 jod_brain_main.py --loop --interval 600
```

## Testes
```bash
cd ~/JOD_ROBO && pytest tests/ -v
```

## Estrutura
```
JOD_ROBO/
├── jod_brain_main.py    # Entry point principal
├── jod_brain/
│   ├── agents/          # Arquiteto, Executor, Revisor
│   ├── io/              # write_file, git_commit_push
│   ├── llm/             # Groq + fallback Ollama
│   ├── memory/          # Memória persistente com lock
│   └── security/        # safe_path, validate_python
├── tests/               # Testes unitários pytest
├── agents/              # Agentes criados pelo JOD
├── scripts/             # Scripts criados pelo JOD
├── apps/                # Apps criadas pelo JOD
├── .jod_memory.json     # Memória persistente
└── requirements.txt     # Dependências
```

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| GROQ_API_KEY | obrigatório | Chave da API Groq |
| OLLAMA_HOST | http://127.0.0.1:11434 | URL do Ollama |
| OLLAMA_MODEL | llama3.2:1b | Modelo Ollama fallback |

## Segurança

- Whitelist de extensões permitidas
- Bloqueio de path traversal
- Validação de sintaxe Python antes de escrever
- Arquivos críticos protegidos (app/main.py, etc)
- Logs de auditoria para tentativas de violação

## Troubleshooting

| Erro | Solução |
|---|---|
| ModuleNotFoundError | pip3 install tenacity pydantic |
| GROQ_API_KEY nao configurada | export GROQ_API_KEY="..." |
| SecurityError: Path traversal | LLM gerou path inválido — revise o prompt |
| Git push falhou | Verifique credenciais git e conexão |
| Timeout no loop | Aumente --interval ou verifique rede |

## LLM

- **Primário**: Groq llama-3.3-70b-versatile (rápido, online)
- **Fallback**: Ollama llama3.2:1b (lento, offline)

---
JOD_ROBO v3.0 — De 1.6/10 para 10/10.
