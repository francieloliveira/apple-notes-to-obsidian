#!/usr/bin/env python3
"""
config.example.py
Template de configuração para o VaultAI.

Copie para config.py e ajuste os valores:
    cp config.example.py config.py
"""

import os

# ─── Paths ───────────────────────────────────────────────────────────────────
# Caminho para o vault Obsidian
VAULT_PATH = os.getenv("VAULT_PATH", os.path.expanduser("~/VaultAI"))

# Diretório onde os scripts serão instalados
SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", "/usr/local/bin")

# ─── Timezone ────────────────────────────────────────────────────────────────
TIMEZONE = "America/Sao_Paulo"

# ─── Pastas que devem ser "achatadas" (sem subpastas no vault)
FLAT_FOLDERS = {"notes", "notas", "todas (icloud)", "all icloud", "icloud"}

# ─── Domínios para organização automática ────────────────────────────────────
# Edite conforme necessário para seu caso de uso
DOMAIN_KEYWORDS = {
    "tech": ["python", "java", "javascript", "docker", "kubernetes"],
    "cloud": ["aws", "azure", "gcp", "lambda", "s3"],
    "ai": ["llm", "machine learning", "transformer", "embedding"],
    "devops": ["ci/cd", "pipeline", "deploy", "terraform"],
    # Adicione seus próprios domínios aqui
}
