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

# ─── Estado local (logs, checkpoints, arquivos de status) ────────────────────
# Tudo fica fora do repositório, em ~/.vault/ (ver README_SETUP.md)
STATE_DIR = os.path.expanduser("~/.vault")

SYNC_LOG = os.path.join(STATE_DIR, "sync.log")
PIPELINE_LOG = os.path.join(STATE_DIR, "pipeline.log")
ORGANIZE_LOG = os.path.join(STATE_DIR, "organize.log")

STATE_FILE = os.path.join(STATE_DIR, "notes.state.json")
IDS_FILE = os.path.join(STATE_DIR, "notes_ids.json")
DIRTY_FILE = os.path.join(STATE_DIR, "dirty.json")
CHECKPOINT_FILE = os.path.join(STATE_DIR, "sync.checkpoint.json")
PATHS_FILE = os.path.join(STATE_DIR, "paths.json")
PROGRESS_FILE = os.path.join(STATE_DIR, "progress.json")
STATUS_FILE = os.path.join(STATE_DIR, "status.json")
METRICS_FILE = os.path.join(STATE_DIR, "metrics.json")
ORGANIZE_METRICS_FILE = os.path.join(STATE_DIR, "organize_metrics.json")
LOCK_FILE = os.path.join(STATE_DIR, "pipeline.lock")

# Toggles de preferência lidos pelo menu bar
SYNC_PAUSED_FILE = os.path.join(STATE_DIR, "sync_paused")
LOGIN_DISABLED_FILE = os.path.join(STATE_DIR, "login_disabled")

# Rotação de logs grandes
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUPS = 3

# ─── LaunchAgents (menu bar) ───────────────────────────────────────────────────
_LAUNCHAGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
PIPELINE_LABEL = "com.vaultai.pipeline"
MENUBAR_LABEL = "com.vaultai.menubar"
LEGACY_MENUBAR_LABEL = "com.franciel.vault-menubar"
AGENT_PLIST = os.path.join(_LAUNCHAGENTS_DIR, f"{PIPELINE_LABEL}.plist")
MENUBAR_PLIST = os.path.join(_LAUNCHAGENTS_DIR, f"{MENUBAR_LABEL}.plist")

# Intervalo do sync automático (segundos) — mantenha igual ao StartInterval do install.sh
PIPELINE_INTERVAL_SECS = 1800  # 30 min

# Intervalo de poll da UI da menu bar (segundos)
POLL_SECS = 2

# ─── Sync (notes_to_obsidian.py) ──────────────────────────────────────────────
# Subpasta dentro de VAULT_PATH onde as notas sincronizadas são gravadas (vazio = raiz)
SYNC_ROOT = ""

# Threads paralelas para buscar conteúdo das notas via AppleScript
FETCH_WORKERS = 6

# Persiste checkpoint a cada N notas gravadas
CHECKPOINT_EVERY = 20

# Timeout (segundos) de cada etapa do pipeline (sync / organize)
STEP_TIMEOUT = 900

# ─── Timezone ────────────────────────────────────────────────────────────────
TIMEZONE = "America/Sao_Paulo"

# ─── Pastas que devem ser "achatadas" (sem subpastas no vault)
FLAT_FOLDERS = {"notes", "notas", "todas (icloud)", "all icloud", "icloud"}

# ─── Organize (organize_vault.py) ─────────────────────────────────────────────
# Pasta para onde notas consideradas "lixo" são movidas
LIXO_DIR = "_Lixo"

# Padrões de nome (regex) tratados como lixo, ex.: notas sem título
LIXO_NAME_PATTERNS = [
    r"^Nova nota$",
    r"^Sem t[íi]tulo$",
    r"^Untitled$",
]

# Notas com menos que isso de conteúdo "real" (sem contar links/headers) viram lixo
MIN_CONTENT_CHARS = 10

# Título precisa ter pelo menos isso de caracteres para contar como citado em outra nota
MIN_TITLE_CHARS = 3

# Teto de links inline automáticos por nota
MAX_INLINE_LINKS = 5

# ─── Domínios para organização automática ────────────────────────────────────
# Edite conforme necessário para seu caso de uso
DOMAIN_KEYWORDS = {
    "tech": ["python", "java", "javascript", "docker", "kubernetes"],
    "cloud": ["aws", "azure", "gcp", "lambda", "s3"],
    "ai": ["llm", "machine learning", "transformer", "embedding"],
    "devops": ["ci/cd", "pipeline", "deploy", "terraform"],
    # Adicione seus próprios domínios aqui
}
