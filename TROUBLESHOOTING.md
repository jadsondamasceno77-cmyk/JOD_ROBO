# 🦞 OpenClaw Troubleshooting: "Unrecognized key: enabled" and Hangs

If your OpenClaw hangs at **"Waiting for agent reply"** or encounters configuration validation errors, follow this guide.

## 1. Configuration Error: `Unrecognized key: enabled`

The command `openclaw config set gateway.auth.enabled false` does not work in OpenClaw 2026.x.
The correct key is now `mode`.

### How to fix:
```bash
# The 'none' mode disables authentication in the gateway.
openclaw config set gateway.auth.mode none
openclaw config set gateway.mode local

# IMPORTANT: Sync the service to apply configuration changes to the daemon:
openclaw gateway install --force
openclaw gateway restart
```

---

## 2. Hanging at "Waiting for agent reply"

This usually happens for two reasons:

1.  **Ollama Disconnected:** If Ollama is not running (or port `11434` is inaccessible), OpenClaw cannot send the request and waits indefinitely.
2.  **Incompatible Model:** Small models (like `llama3.2:1b`) might hang when trying to process OpenClaw's complex system prompt.

### How to diagnose and resolve:

1.  **Verify Ollama:**
    ```bash
    curl -s http://127.0.0.1:11434/api/tags
    # If it returns nothing or an error, Ollama is not running.
    ```

2.  **Monitor real-time logs:**
    In a separate terminal, run:
    ```bash
    openclaw logs --follow
    ```
    This will show the exact communication error (e.g., `Connection refused` or `Context length exceeded`).

3.  **Use the Auto-Fix Script:**
    We provide a `fix_openclaw.sh` script that applies configuration fixes and verifies Ollama connectivity:
    ```bash
    chmod +x fix_openclaw.sh
    ./fix_openclaw.sh
    ```
