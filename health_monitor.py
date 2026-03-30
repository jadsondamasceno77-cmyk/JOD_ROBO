#!/usr/bin/env python3
"""JOD_ROBO — Health Monitor. Verifica 4 serviços a cada 60s."""
import subprocess, time, requests, logging
from datetime import datetime
logging.basicConfig(filename="health.log", level=logging.INFO,
    format="%(asctime)s %(message)s")

SERVICES = ["jod-factory","jod-viewer","eli-api","n8n"]
PORTS    = {"37777":"factory","37778":"viewer","37779":"eli-api","5678":"n8n"}

def check():
    issues = []
    for svc in SERVICES:
        r = subprocess.run(["systemctl","is-active",svc], capture_output=True, text=True)
        if r.stdout.strip() != "active":
            issues.append(f"{svc} INATIVO")
            subprocess.run(["sudo","systemctl","restart",svc])
            logging.warning(f"RESTART: {svc}")
    for port, name in PORTS.items():
        try:
            requests.get(f"http://localhost:{port}/health", timeout=3)
        except:
            issues.append(f"porta {port} ({name}) sem resposta")
    if issues:
        logging.error("ISSUES: " + " | ".join(issues))
    else:
        logging.info("OK — todos os serviços saudáveis")

if __name__ == "__main__":
    print("Health monitor iniciado. Ctrl+C para parar.")
    while True:
        check()
        time.sleep(60)
