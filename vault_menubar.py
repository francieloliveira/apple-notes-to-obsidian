#!/usr/bin/env python3
"""
vault_menubar.py — VaultAI menu bar app
Requer: pip install rumps

Mostra o estado do pipeline na menu bar do macOS.
Ícones:
  ⟳  sincronizando
  ✓  ok / atualizado
  ✕  erro
  ·  idle (nenhum sync ainda)
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import rumps

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────────────────
STATUS_FILE  = os.path.expanduser("~/.vault/status.json")
PIPELINE     = "${SCRIPTS_DIR}/pipeline.py"
LOG_FILE     = os.path.expanduser("~/.vault/pipeline.log")
SYNC_LOG     = os.path.expanduser("~/.vault/sync.log")
POLL_SECS    = 5      # intervalo de leitura do status.json
# ─────────────────────────────────────────────────────────────────────────────

# Ícones usados no título da menu bar
ICON = {
    "idle":    "📓",
    "running": "⟳",
    "ok":      "✓",
    "error":   "✕",
}

# Sons
SOUND_OK    = "Glass"
SOUND_ERROR = "Basso"


class VaultMenuBar(rumps.App):

    def __init__(self):
        super().__init__(
            name="VaultAI",
            title=ICON["idle"],
            quit_button=None,   # customizamos o quit abaixo
        )

        # ── Itens do menu ──────────────────────────────────────────────────
        self.status_item   = rumps.MenuItem("Aguardando primeiro sync…")
        self.status_item.set_callback(None)   # não clicável

        self.last_sync_item = rumps.MenuItem("—")
        self.last_sync_item.set_callback(None)

        sep1 = rumps.separator

        self.sync_now      = rumps.MenuItem("Sincronizar agora",        callback=self.run_sync)
        self.full_sync     = rumps.MenuItem("Sync completo (--full)",   callback=self.run_full_sync)
        self.dry_run_item  = rumps.MenuItem("Dry run (simular)",        callback=self.run_dry_run)

        sep2 = rumps.separator

        self.open_log      = rumps.MenuItem("Ver log do pipeline",      callback=self.open_pipeline_log)
        self.open_sync_log = rumps.MenuItem("Ver log do sync",          callback=self.open_sync_log_cb)
        self.open_vault    = rumps.MenuItem("Abrir vault no Finder",    callback=self.open_vault_cb)

        sep3 = rumps.separator

        self.quit_item     = rumps.MenuItem("Sair do VaultAI",          callback=self.quit_app)

        self.menu = [
            self.status_item,
            self.last_sync_item,
            rumps.separator,
            self.sync_now,
            self.full_sync,
            self.dry_run_item,
            rumps.separator,
            self.open_log,
            self.open_sync_log,
            self.open_vault,
            rumps.separator,
            self.quit_item,
        ]

        # Estado interno
        self._last_state    = "idle"
        self._running       = False
        self._last_updated  = None

        # Inicia polling em thread separada
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    # ── Polling do status.json ─────────────────────────────────────────────

    def _poll_loop(self):
        while True:
            self._refresh_status()
            time.sleep(POLL_SECS)

    def _refresh_status(self):
        data = self._read_status()
        state   = data.get("state", "idle")
        message = data.get("message", "")
        updated = data.get("updated_at", "")
        metrics = data.get("metrics", {})

        # Não atualiza se nada mudou
        if updated == self._last_updated and state == self._last_state:
            return

        self._last_updated = updated
        self._last_state   = state

        # Ícone na menu bar
        icon = ICON.get(state, "·")

        # Adiciona contagem de notas no ícone se houver métricas
        criadas     = metrics.get("criadas", 0)
        atualizadas = metrics.get("atualizadas", 0)
        total_new   = criadas + atualizadas

        if state == "ok" and total_new > 0:
            self.title = f"{icon} {total_new}"
        elif state == "running":
            self.title = f"{icon} …"
        elif state == "error":
            self.title = f"{icon}"
        else:
            self.title = icon

        # Texto do item de status
        if state == "running":
            self.status_item.title = f"⟳  {message or 'Sincronizando…'}"
        elif state == "ok":
            elapsed = metrics.get("elapsed_s", 0)
            self.status_item.title = f"✓  {message or 'Atualizado'}"
        elif state == "error":
            self.status_item.title = f"✕  {message or 'Erro no pipeline'}"
        else:
            self.status_item.title = "Aguardando sync…"

        # Última sincronização
        if updated:
            try:
                dt  = datetime.fromisoformat(updated)
                rel = self._relative_time(dt)
                self.last_sync_item.title = f"   último sync: {rel}"
            except Exception:
                self.last_sync_item.title = f"   {updated[:16]}"

        # Habilita/desabilita botões durante execução
        is_running = (state == "running")
        self.sync_now.set_callback(None if is_running else self.run_sync)
        self.full_sync.set_callback(None if is_running else self.run_full_sync)
        self.dry_run_item.set_callback(None if is_running else self.run_dry_run)

    def _read_status(self) -> dict:
        try:
            p = Path(STATUS_FILE)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _relative_time(self, dt: datetime) -> str:
        delta = datetime.now() - dt
        s = int(delta.total_seconds())
        if s < 60:      return "agora mesmo"
        if s < 3600:    return f"há {s // 60} min"
        if s < 86400:   return f"há {s // 3600}h"
        return f"há {s // 86400}d"

    # ── Ações do menu ──────────────────────────────────────────────────────

    def _run_pipeline(self, extra_args: list, label: str):
        if self._running:
            rumps.notification("VaultAI", "Pipeline em execução",
                               "Aguarde o sync atual terminar.")
            return
        self._running = True
        self.title = f"{ICON['running']} …"
        self.status_item.title = f"⟳  {label}…"

        def worker():
            try:
                cmd = ["/usr/bin/python3", PIPELINE] + extra_args
                subprocess.run(cmd, timeout=800)
            except Exception as e:
                rumps.notification("VaultAI", "Erro", str(e))
            finally:
                self._running = False
                self._last_updated = None  # força refresh

        threading.Thread(target=worker, daemon=True).start()

    @rumps.clicked("Sincronizar agora")
    def run_sync(self, _=None):
        self._run_pipeline([], "Sincronizando")

    def run_full_sync(self, _):
        self._run_pipeline(["--full"], "Sync completo")

    def run_dry_run(self, _):
        self._run_pipeline(["--dry-run"], "Simulando")

    # ── Ações de log / vault ───────────────────────────────────────────────

    def open_pipeline_log(self, _):
        self._open_in_terminal(LOG_FILE)

    def open_sync_log_cb(self, _):
        self._open_in_terminal(SYNC_LOG)

    def open_vault_cb(self, _):
        vault = os.path.expanduser(
            "~/ValtAI/ValtAI"  # ajuste se necessário
        )
        subprocess.Popen(["open", vault])

    def _open_in_terminal(self, path: str):
        script = f'tell application "Terminal" to do script "tail -100 {path}"'
        subprocess.Popen(["osascript", "-e", script])

    def quit_app(self, _):
        rumps.quit_application()

    # ── Timer para animar o ícone durante sync ─────────────────────────────

    @rumps.timer(2)
    def animate_running(self, _):
        """Alterna caracteres de spinner enquanto pipeline roda."""
        if self._last_state != "running":
            return
        frames = ["⟳", "↻"]
        idx = int(time.time()) % len(frames)
        current = self.title.split(" ")[0] if " " in self.title else self.title
        self.title = f"{frames[idx]} …"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Verifica dependência
    try:
        import rumps  # noqa
    except ImportError:
        print("Instale rumps: pip install rumps")
        raise

    VaultMenuBar().run()
