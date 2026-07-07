#!/usr/bin/env bash
# VaultAI — instalação unificada (sem sudo: roda direto do diretório do projeto)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="${SCRIPTS_DIR:-${PROJECT_DIR}}"
STATE_DIR="${HOME}/.vault"
LAUNCHAGENTS_DIR="${HOME}/Library/LaunchAgents"
VENV="${PROJECT_DIR}/.venv"
PYTHON="${VENV}/bin/python3"

echo "==> VaultAI install"
echo "    Projeto: ${PROJECT_DIR}"
echo "    Scripts: ${SCRIPTS_DIR}"

# ── 1. Virtualenv + dependências ─────────────────────────────────────────────
if [[ ! -x "${PYTHON}" ]]; then
  echo "==> Criando venv em ${VENV}"
  python3 -m venv "${VENV}"
fi

echo "==> Instalando dependências"
"${PYTHON}" -m pip install --upgrade pip -q
"${PYTHON}" -m pip install -r "${PROJECT_DIR}/requirements.txt" -q
"${PYTHON}" -c "import rumps, markdownify; print('    OK: rumps + markdownify')"

# ── 2. Permissões de execução ────────────────────────────────────────────────
chmod +x "${PROJECT_DIR}/pipeline.py" \
         "${PROJECT_DIR}/notes_to_obsidian.py" \
         "${PROJECT_DIR}/organize_vault.py" \
         "${PROJECT_DIR}/vault_menubar.py"

# ── 3. Estado local ──────────────────────────────────────────────────────────
mkdir -p "${STATE_DIR}"
mkdir -p "${HOME}/Applications"
echo "==> Criando atalho de reinício"
"${PYTHON}" -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}')
from vault_menubar import ensure_launcher
print('    Atalho:', ensure_launcher())
"

# ── 4. LaunchAgents ───────────────────────────────────────────────────────────
PIPELINE_LABEL="com.vaultai.pipeline"
MENUBAR_LABEL="com.vaultai.menubar"
LEGACY_LABEL="com.franciel.vault-menubar"

unload_agent() {
  local label="$1"
  local plist="${LAUNCHAGENTS_DIR}/${label}.plist"
  if launchctl list "${label}" &>/dev/null; then
    launchctl unload "${plist}" 2>/dev/null \
      || launchctl bootout "gui/$(id -u)" "${plist}" 2>/dev/null \
      || true
    echo "    Descarregado: ${label}"
  fi
}

echo "==> Configurando LaunchAgents"
unload_agent "${PIPELINE_LABEL}"
unload_agent "${MENUBAR_LABEL}"
unload_agent "${LEGACY_LABEL}"

cat > "${LAUNCHAGENTS_DIR}/${PIPELINE_LABEL}.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>          <string>${PIPELINE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPTS_DIR}/pipeline.py</string>
    </array>
    <key>StartInterval</key>  <integer>1800</integer>
    <key>RunAtLoad</key>      <false/>
    <key>StandardOutPath</key><string>${STATE_DIR}/launchd.log</string>
    <key>StandardErrorPath</key><string>${STATE_DIR}/launchd.log</string>
</dict>
</plist>
EOF

cat > "${LAUNCHAGENTS_DIR}/${MENUBAR_LABEL}.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>             <string>${MENUBAR_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPTS_DIR}/vault_menubar.py</string>
    </array>
    <key>RunAtLoad</key>         <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>   <string>${STATE_DIR}/menubar.log</string>
    <key>StandardErrorPath</key> <string>${STATE_DIR}/menubar.log</string>
</dict>
</plist>
EOF

rm -f "${LAUNCHAGENTS_DIR}/${LEGACY_LABEL}.plist"

launchctl load "${LAUNCHAGENTS_DIR}/${PIPELINE_LABEL}.plist"
launchctl load "${LAUNCHAGENTS_DIR}/${MENUBAR_LABEL}.plist"
echo "    Carregados: ${PIPELINE_LABEL}, ${MENUBAR_LABEL}"

# ── 5. Rotação de logs grandes ───────────────────────────────────────────────
echo "==> Verificando rotação de logs"
cd "${PROJECT_DIR}"
"${PYTHON}" -c "
from utils import rotate_logs_in_dir
from config import STATE_DIR, LOG_MAX_BYTES, LOG_BACKUPS
n = rotate_logs_in_dir(STATE_DIR, max_bytes=LOG_MAX_BYTES, backups=LOG_BACKUPS)
print(f'    Rotacionados: {n} arquivo(s)' if n else '    Nenhum log precisou rotacionar')
"

echo ""
echo "✓ Instalação concluída"
echo "  Python:   ${PYTHON}"
echo "  Scripts:  ${SCRIPTS_DIR}/"
echo "  Logs:     ${STATE_DIR}/"
echo "  Reinstalar: ${PROJECT_DIR}/install.sh"