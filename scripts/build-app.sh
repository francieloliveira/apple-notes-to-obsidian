#!/usr/bin/env bash
# Monta VaultAI.app a partir do pacote Swift (sem Xcode project).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${1:-release}"
APP="${ROOT}/build/VaultAI.app"

echo "==> Compilando VaultAI (${CONFIG})"
swift build -c "${CONFIG}" --product VaultAI --package-path "${ROOT}"

BIN_DIR="$(swift build -c "${CONFIG}" --show-bin-path --package-path "${ROOT}")"
BIN="${BIN_DIR}/VaultAI"
if [[ ! -x "${BIN}" ]]; then
  echo "binário não encontrado: ${BIN}" >&2
  exit 1
fi

echo "==> Montando ${APP}"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
cp "${BIN}" "${APP}/Contents/MacOS/VaultAI"
cp "${ROOT}/Resources/Info.plist" "${APP}/Contents/Info.plist"

if [[ -f "${ROOT}/VaultAI.icns" ]]; then
  cp "${ROOT}/VaultAI.icns" "${APP}/Contents/Resources/VaultAI.icns"
fi

chmod +x "${APP}/Contents/MacOS/VaultAI"

# Assinatura ad-hoc: suficiente para uso local e para o TCC do Apple Events.
codesign --force --deep --sign - "${APP}" >/dev/null 2>&1 || true

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[[ -x "${LSREGISTER}" ]] && "${LSREGISTER}" -f "${APP}" || true

echo "✓ App pronto: ${APP}"
