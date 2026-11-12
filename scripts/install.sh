#!/usr/bin/env bash
# Instala o VaultAI nativo em ~/Applications e remove os LaunchAgents antigos
# do pipeline Python (o app Swift agenda o sync sozinho).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${ROOT}/build/VaultAI.app"
TARGET="${HOME}/Applications/VaultAI.app"
VISIBLE="/Applications/VaultAI.app"

"${ROOT}/scripts/build-app.sh" release

echo "==> Instalando em ${TARGET}"
mkdir -p "${HOME}/Applications"
pkill -f "${TARGET}/Contents/MacOS/VaultAI" >/dev/null 2>&1 || true
rm -rf "${TARGET}"
ditto "${APP}" "${TARGET}"

# Remove agentes antigos para não sincronizar duas vezes.
for label in com.vaultai.pipeline com.vaultai.menubar com.franciel.vault-menubar; do
  plist="${HOME}/Library/LaunchAgents/${label}.plist"
  launchctl bootout "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
  launchctl unload "${plist}" >/dev/null 2>&1 || true
  rm -f "${plist}"
done
pkill -f "vault_menubar.py" >/dev/null 2>&1 || true
pkill -f "pipeline.py" >/dev/null 2>&1 || true

# Atalho na pasta Aplicativos do Finder, quando possível.
if [[ -w /Applications ]]; then
  if [[ -e "${VISIBLE}" && ! -L "${VISIBLE}" ]]; then
    bid="$(defaults read "${VISIBLE}/Contents/Info" CFBundleIdentifier 2>/dev/null || true)"
    if [[ "${bid}" == "com.vaultai.app" ]]; then rm -rf "${VISIBLE}"; fi
  fi
  ln -sfn "${TARGET}" "${VISIBLE}"
  echo "    Finder: ${VISIBLE}"
fi

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[[ -x "${LSREGISTER}" ]] && "${LSREGISTER}" -f "${TARGET}" || true

echo "✓ Instalado"
echo "  Abrir: open ${TARGET}"
echo "  Estado: ${HOME}/.vault"
