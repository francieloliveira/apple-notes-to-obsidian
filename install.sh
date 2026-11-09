#!/usr/bin/env bash
# VaultAI — instalação unificada (sem sudo: roda direto do diretório do projeto)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="${SCRIPTS_DIR:-${PROJECT_DIR}}"
STATE_DIR="${HOME}/.vault"
LAUNCHAGENTS_DIR="${HOME}/Library/LaunchAgents"

# A janela não herda o venv. Este interpreter tem que importar site.
APP_PYTHON="/usr/bin/python3"
if [[ "${APP_PYTHON}" == *"/.venv/"* ]]; then
  echo "interpreter da janela não pode ficar debaixo de .venv" >&2
  exit 1
fi
if ! "${APP_PYTHON}" -c 'import site' >/dev/null 2>&1; then
  echo "interpreter da janela não importa site: ${APP_PYTHON}" >&2
  exit 1
fi

echo "==> VaultAI install"
echo "    Projeto: ${PROJECT_DIR}"
echo "    Scripts: ${SCRIPTS_DIR}"
echo "    Janela:  ${APP_PYTHON}"

chmod +x "${PROJECT_DIR}/pipeline.py" \
         "${PROJECT_DIR}/notes_to_obsidian.py" \
         "${PROJECT_DIR}/organize_vault.py" \
         "${PROJECT_DIR}/vaultai_dashboard.py" \
         "${PROJECT_DIR}/vault_menubar.py"

mkdir -p "${STATE_DIR}"
mkdir -p "${HOME}/Applications"
echo "==> Gerando VaultAI.app"
rm -f "${HOME}/Applications/VaultAI.app/Contents/MacOS/launcher"
"${APP_PYTHON}" -c "
import sys
sys.path.insert(0, sys.argv[1])
from vaultai_dashboard import ensure_app
print('    App:', ensure_app(python=sys.argv[2]))
" "${PROJECT_DIR}" "${APP_PYTHON}"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "${LSREGISTER}" ]]; then
  "${LSREGISTER}" -f "${HOME}/Applications/VaultAI.app" || true
fi

# Prova da janela não pode reescrever o LaunchAgent. O venv do pipeline vem depois.
if [[ "${VAULTAI_APP_ONLY:-}" == "1" ]]; then
  echo "    App gerado; pipeline e LaunchAgent não alterados"
  exit 0
fi

# Venv só para o LaunchAgent. No iCloud não fica dentro do projeto.
# Arquivo dataless não é ausente (não recriar por cima) nem executável válido.
VENV="$("${APP_PYTHON}" -c "
import sys
sys.path.insert(0, sys.argv[1])
from vaultai_dashboard import pipeline_venv_dir
print(pipeline_venv_dir(sys.argv[1]))
" "${PROJECT_DIR}")"
PYTHON="${VENV}/bin/python3"
echo "    Pipeline venv: ${VENV}"

if ! "${APP_PYTHON}" -c "
import sys
sys.path.insert(0, sys.argv[1])
from vaultai_dashboard import path_on_icloud
raise SystemExit(2 if path_on_icloud(sys.argv[2]) else 0)
" "${PROJECT_DIR}" "${VENV}"; then
  echo "não crio venv em árvore iCloud: ${VENV}" >&2
  exit 1
fi

if [[ -e "${PYTHON}" ]] && "${APP_PYTHON}" -c "
import sys
sys.path.insert(0, sys.argv[1])
from vaultai_dashboard import is_dataless
raise SystemExit(0 if is_dataless(sys.argv[2]) else 1)
" "${PROJECT_DIR}" "${PYTHON}"; then
  echo "python dataless não é executável válido: ${PYTHON}" >&2
  exit 1
fi

if [[ ! -e "${PYTHON}" ]]; then
  echo "==> Criando venv em ${VENV}"
  mkdir -p "$(dirname "${VENV}")"
  "${APP_PYTHON}" -m venv "${VENV}"
fi

echo "==> Instalando dependências"
"${PYTHON}" -m pip install --upgrade pip -q
"${PYTHON}" -m pip install -r "${PROJECT_DIR}/requirements.txt" -q
"${PYTHON}" -c "import rumps, markdownify; print('    OK: rumps + markdownify')"

# ── LaunchAgents ─────────────────────────────────────────────────────────────
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

PIPELINE_INTERVAL_SECS="$("${PYTHON}" -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}')
from config_import import require
(interval,) = require('PIPELINE_INTERVAL_SECS')
print(interval)
")"
if [[ ! "${PIPELINE_INTERVAL_SECS}" =~ ^[0-9]+$ ]]; then
  echo "PIPELINE_INTERVAL_SECS inválido: '${PIPELINE_INTERVAL_SECS}'" >&2
  exit 1
fi

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
    <key>StartInterval</key>  <integer>${PIPELINE_INTERVAL_SECS}</integer>
    <key>RunAtLoad</key>      <false/>
    <key>StandardOutPath</key><string>${STATE_DIR}/launchd.log</string>
    <key>StandardErrorPath</key><string>${STATE_DIR}/launchd.log</string>
</dict>
</plist>
EOF

rm -f "${LAUNCHAGENTS_DIR}/${LEGACY_LABEL}.plist"

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

launchctl load "${LAUNCHAGENTS_DIR}/${PIPELINE_LABEL}.plist"
echo "    Carregado: ${PIPELINE_LABEL}"
launchctl load "${LAUNCHAGENTS_DIR}/${MENUBAR_LABEL}.plist"
echo "    Carregado: ${MENUBAR_LABEL}"

# ── Rotação de logs grandes ──────────────────────────────────────────────────
echo "==> Verificando rotação de logs"
cd "${PROJECT_DIR}"
"${PYTHON}" -c "
from config_import import require
from utils import rotate_logs_in_dir
STATE_DIR, LOG_MAX_BYTES, LOG_BACKUPS = require(
    'STATE_DIR', 'LOG_MAX_BYTES', 'LOG_BACKUPS',
)
n = rotate_logs_in_dir(STATE_DIR, max_bytes=LOG_MAX_BYTES, backups=LOG_BACKUPS)
print(f'    Rotacionados: {n} arquivo(s)' if n else '    Nenhum log precisou rotacionar')
"

echo ""
echo "✓ Instalação concluída"
echo "  Janela:   ${APP_PYTHON}"
echo "  Menu bar: ${PYTHON} ${SCRIPTS_DIR}/vault_menubar.py"
echo "  Pipeline: ${PYTHON}"
echo "  Scripts:  ${SCRIPTS_DIR}/"
echo "  Logs:     ${STATE_DIR}/"
echo "  Reinstalar: ${PROJECT_DIR}/install.sh"
