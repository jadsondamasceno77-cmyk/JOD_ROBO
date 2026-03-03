FROM python:3.11-slim

WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# copia tudo (inclui ./aplicativo)
COPY . /workspace

# instala dependências (prioriza requirements dentro de /workspace/aplicativo)
RUN pip install --no-cache-dir -U pip && \
    if [ -f /workspace/aplicativo/requirements.txt ]; then \
        pip install --no-cache-dir -r /workspace/aplicativo/requirements.txt; \
    elif [ -f /workspace/requirements.txt ]; then \
        pip install --no-cache-dir -r /workspace/requirements.txt; \
    elif [ -f /workspace/aplicativo/pyproject.toml ]; then \
        pip install --no-cache-dir -e /workspace/aplicativo; \
    else \
        echo "ERRO: Não encontrei requirements.txt nem pyproject.toml"; \
        echo "Conteúdo /workspace:"; ls -la /workspace; \
        echo "Conteúdo /workspace/aplicativo:"; ls -la /workspace/aplicativo || true; \
        exit 1; \
    fi

EXPOSE 8000

CMD ["sh", "/workspace/start.sh"]
