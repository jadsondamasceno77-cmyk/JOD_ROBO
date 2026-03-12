# 🦞 Solução para OpenClaw: "Unrecognized key: enabled" e Travamentos

Se o seu OpenClaw trava em **"Waiting for agent reply"** ou dá erro de validação na configuração, siga este guia.

## 1. Erro de Configuração: `Unrecognized key: enabled`

O comando `openclaw config set gateway.auth.enabled false` não funciona em versões recentes.
A chave correta agora é `mode`.

### Como corrigir:
```bash
# O modo 'none' desabilita a autenticação no gateway.
openclaw config set gateway.auth.mode none
openclaw config set gateway.mode local

# Se você estiver usando systemd, sincronize o serviço:
openclaw gateway install --force
openclaw gateway restart
```

---

## 2. Travamento em "Waiting for agent reply"

Isso geralmente ocorre por dois motivos:

1.  **Ollama Desconectado:** Se o Ollama não estiver rodando (ou a porta `11434` estiver inacessível), o OpenClaw não consegue enviar a requisição e fica esperando indefinidamente.
2.  **Modelo Incompatível:** Modelos muito pequenos (como `llama3.2:1b`) podem travar ao tentar processar o prompt de sistema complexo do OpenClaw.

### Como diagnosticar e resolver:

1.  **Verifique o Ollama:**
    ```bash
    curl -s http://127.0.0.1:11434/api/tags
    # Se não retornar nada, rode:
    ollama serve
    ```

2.  **Monitore os logs reais:**
    Em um terminal separado, rode:
    ```bash
    openclaw logs --follow
    ```
    Isso mostrará o erro exato de comunicação (ex: `Connection refused` ou `Context length exceeded`).

3.  **Use o Script de Correção Automática:**
    Fornecemos um script `fix_openclaw.sh` que faz as correções de configuração e verifica a conectividade com o Ollama:
    ```bash
    chmod +x fix_openclaw.sh
    ./fix_openclaw.sh
    ```
