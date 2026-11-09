#!/usr/bin/env python3
"""
config.example.py
Template de configuração para o VaultAI.

Copie para config.py e ajuste os paths:
    cp config.example.py config.py

config.py é local e não entra no git. Este arquivo é o template:
um clone que faz essa cópia consegue importar os scripts.
"""

import os

# ─── Paths ───────────────────────────────────────────────────────────────────
# Default: o diretório deste arquivo (config.py depois da cópia), não um home fixo.
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))

VAULTAI_HOME = os.getenv("VAULTAI_HOME", _CONFIG_DIR)

# Caminho para o vault Obsidian
VAULT_PATH = os.getenv("VAULT_PATH", os.path.expanduser("~/VaultAI"))

# Diretório dos scripts (padrão: o próprio repositório)
SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", VAULTAI_HOME)

# Estado local (logs, lock de progresso, métricas). Não é o vault.
STATE_DIR = os.path.expanduser("~/.vault")

# Interpreter da janela. O venv do pipeline, se o install criar um, entra só
# no plist do LaunchAgent — não aqui, e nunca em .venv dentro deste repositório
# (no iCloud esse path fica dataless e o .app não abre).
PYTHON_BIN = os.getenv("VAULTAI_PYTHON", "/usr/bin/python3")

# Arquivos de estado
STATE_FILE = os.path.join(STATE_DIR, "notes_state.json")
IDS_FILE = os.path.join(STATE_DIR, "notes_ids.json")
DIRTY_FILE = os.path.join(STATE_DIR, "vault_dirty.json")
CHECKPOINT_FILE = os.path.join(STATE_DIR, "sync_checkpoint.json")
METRICS_FILE = os.path.join(STATE_DIR, "metrics.json")
ORGANIZE_METRICS_FILE = os.path.join(STATE_DIR, "organize_metrics.json")
PATHS_FILE = os.path.join(STATE_DIR, "note_paths.json")
STATUS_FILE = os.path.join(STATE_DIR, "status.json")
SYNC_PAUSED_FILE = os.path.join(STATE_DIR, "sync_paused")
LOGIN_DISABLED_FILE = os.path.join(STATE_DIR, "login_disabled")
PROGRESS_FILE = os.path.join(STATE_DIR, "progress.json")

# Logs
SYNC_LOG = os.path.join(STATE_DIR, "sync.log")
ORGANIZE_LOG = os.path.join(STATE_DIR, "organize.log")
PIPELINE_LOG = os.path.join(STATE_DIR, "pipeline.log")
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB antes de rotacionar
LOG_BACKUPS = 3

# Atalho para reabrir o menu bar (criado pelo install.sh)
LAUNCHER_PATH = os.path.expanduser("~/Applications/VaultAI.app")

# Ícone da menu bar (gerado por assets/generate_menubar_icon.py)
MENUBAR_ICON_PATH = os.path.join(VAULTAI_HOME, "assets", "menubar_icon.png")

# ─── Sync ────────────────────────────────────────────────────────────────────
TIMEZONE = "America/Sao_Paulo"
FETCH_WORKERS = 8            # workers paralelos para buscar corpos das notas
CHECKPOINT_EVERY = 50        # salva checkpoint a cada N notas gravadas
SYNC_ROOT = ""               # subpasta dentro do vault (vazio = raiz)

# Pastas do Apple Notes que não geram subpastas no vault
FLAT_FOLDERS = {"notes", "notas", "todas (icloud)", "all icloud", "icloud"}

# ─── Secrets ─────────────────────────────────────────────────────────────────
# Só o interruptor e pastas extras. Os padrões de detecção ficam no código,
# não neste template.
SECRETS_SKIP_ENABLED = True
SECRETS_FOLDER_NAMES = {"senhas", "passwords"}

# ─── Organização ─────────────────────────────────────────────────────────────
LIXO_DIR = "_lixo"
MIN_CONTENT_CHARS = 0        # 0 = detecção por conteúdo desativada (só por nome)
MAX_INLINE_LINKS = 5         # teto de links contextuais por nota
MIN_TITLE_CHARS = 5          # título mínimo para matching por citação no texto

LIXO_NAME_PATTERNS = [
    r"^sem-nome\.md$",
    r"^Nova Nota\.md$",
    r"^New Note\.md$",
    r"^untitled\.md$",
    r"^OK\.md$",
]

# Domínios genéricos. Edite no config.py local; não coloque projetos pessoais aqui.
DOMAIN_KEYWORDS = {
    "tech": ["python", "java", "javascript", "docker", "kubernetes"],
    "cloud": ["aws", "azure", "gcp", "lambda", "s3"],
    "ai": ["llm", "machine learning", "transformer", "embedding"],
    "devops": ["ci/cd", "pipeline", "deploy", "terraform"],
    "sql": ["select", "postgresql", "mysql", "sqlite"],
    "git": ["git commit", "git push", "github", "branch", "pull request"],
    "scrum": ["scrum", "sprint", "backlog", "user story"],
}

# ─── Pipeline ────────────────────────────────────────────────────────────────
STEP_TIMEOUT = 700                 # segundos por etapa
LOCK_FILE = "/tmp/vault_pipeline.lock"
PIPELINE_INTERVAL_SECS = 1800      # intervalo do LaunchAgent (30 min); install.sh lê daqui

# ─── LaunchAgents ────────────────────────────────────────────────────────────
LAUNCHAGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
PIPELINE_LABEL = "com.vaultai.pipeline"
MENUBAR_LABEL = "com.vaultai.menubar"
AGENT_PLIST = os.path.join(LAUNCHAGENTS_DIR, f"{PIPELINE_LABEL}.plist")
MENUBAR_PLIST = os.path.join(LAUNCHAGENTS_DIR, f"{MENUBAR_LABEL}.plist")
LEGACY_MENUBAR_LABEL = "com.vaultai.menubar.legacy"

# ─── Menu bar ────────────────────────────────────────────────────────────────
POLL_SECS = 5  # intervalo de polling do status.json
