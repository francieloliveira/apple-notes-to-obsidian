#!/usr/bin/env python3
"""
config.example.py
Template de configuração para o VaultAI.

Copie para config.py e ajuste os valores:
    cp config.example.py config.py
"""

import os

# ─── Paths ───────────────────────────────────────────────────────────────────
# Repositório local do VaultAI (onde fica o .venv)
VAULTAI_HOME = os.getenv("VAULTAI_HOME", os.path.expanduser("~/IntegraNotesMacObsidian"))

# Caminho para o vault Obsidian
VAULT_PATH = os.getenv("VAULT_PATH", os.path.expanduser("~/VaultAI"))

# Diretório dos scripts (padrão: o próprio repositório)
SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", VAULTAI_HOME)

# Python do venv criado pelo install.sh
PYTHON_BIN = os.getenv("VAULTAI_PYTHON", os.path.join(VAULTAI_HOME, ".venv/bin/python3"))

# Ícone da menu bar (gerado por assets/generate_menubar_icon.py)
MENUBAR_ICON_PATH = os.path.join(VAULTAI_HOME, "assets", "menubar_icon.png")

# Atalho para reabrir o menu bar (criado pelo install.sh)
LAUNCHER_PATH = os.path.expanduser("~/Applications/VaultAI.app")

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
