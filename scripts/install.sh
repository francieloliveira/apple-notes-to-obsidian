#!/usr/bin/env bash
# Instala o VaultAI nativo em /Applications (ou ~/Applications se não houver
# permissão) e remove os LaunchAgents antigos do pipeline Python — o app Swift
# agenda o sync sozinho.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${ROOT}/build/VaultAI.app"

# /Applications é onde o Spotlight e o Finder realmente indexam o app.
if [[ -w /Applications ]]; then
  TARGET="/Applications/VaultAI.app"
else
  TARGET="${HOME}/Applications/VaultAI.app"
fi

"${ROOT}/scripts/build-app.sh" release

echo "==> Instalando em ${TARGET}"
mkdir -p "$(dirname "${TARGET}")"
pkill -f "VaultAI.app/Contents/MacOS/VaultAI" >/dev/null 2>&1 || true
sleep 0.3
rm -rf "${TARGET}"
ditto "${APP}" "${TARGET}"

# Remove instalações antigas (cópia ou symlink) para não duplicar o bundle id.
OLD="${HOME}/Applications/VaultAI.app"
if [[ "${OLD}" != "${TARGET}" && ( -e "${OLD}" || -L "${OLD}" ) ]]; then
  rm -rf "${OLD}"
  echo "    Removido: ${OLD}"
fi

# Remove agentes antigos para não sincronizar duas vezes.
for label in com.vaultai.pipeline com.vaultai.menubar com.franciel.vault-menubar; do
  plist="${HOME}/Library/LaunchAgents/${label}.plist"
  launchctl bootout "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
  launchctl unload "${plist}" >/dev/null 2>&1 || true
  rm -f "${plist}"
done
pkill -f "vault_menubar.py" >/dev/null 2>&1 || true
pkill -f "pipeline.py" >/dev/null 2>&1 || true

# Registra no LaunchServices e força o Spotlight a indexar na hora.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[[ -x "${LSREGISTER}" ]] && "${LSREGISTER}" -f "${TARGET}" || true
mdimport -f "${TARGET}" >/dev/null 2>&1 || true

echo "✓ Instalado"
echo "  Abrir: open ${TARGET}"
echo "  Estado: ${HOME}/.vault"
