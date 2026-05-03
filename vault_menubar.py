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
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    STATUS_FILE, SCRIPTS_DIR, PIPELINE_LOG as LOG_FILE,
    SYNC_LOG, POLL_SECS,
    AGENT_PLIST, MENUBAR_PLIST, PIPELINE_INTERVAL_SECS,
    PROGRESS_FILE,
)

PIPELINE = os.path.join(SCRIPTS_DIR, "pipeline.py")

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

        self.toggle_sync   = rumps.MenuItem("",                          callback=self.toggle_sync_cb)
        self.toggle_login  = rumps.MenuItem("",                          callback=self.toggle_login_cb)
        self.quit_item     = rumps.MenuItem("Sair do VaultAI",           callback=self.quit_app)

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
            self.toggle_sync,
            self.toggle_login,
            rumps.separator,
            self.quit_item,
        ]

        # Atualiza labels dos toggles com o estado real
        self._refresh_toggles()

        # Ao iniciar o menu bar, garante que o pipeline LaunchAgent está ativo.
        # Isso reativa o sync automático caso o menu bar tenha sido fechado e
        # reaberto (o quit_app() descarrega o agente ao sair).
        if self._plist_exists(AGENT_PLIST):
            self._launchctl("load", AGENT_PLIST)

        # Estado interno
        self._last_state    = "idle"
        self._running       = False
        self._last_updated  = None
        self._sync_started  = None   # timestamp de início do sync (para elapsed)
        self._proc          = None   # subprocesso do pipeline em execução

        # Inicia polling em thread separada
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    # ── Polling do status.json ─────────────────────────────────────────────

    def _poll_loop(self):
        """Thread de background: apenas lê arquivos e calcula valores — sem tocar na UI."""
        while True:
            self._compute_status()
            time.sleep(POLL_SECS)

    def _compute_status(self):
        """
        Lê o status.json e calcula os valores a exibir.
        Não faz NENHUMA chamada de UI — pode ser chamado de qualquer thread.
        Os valores calculados ficam em self._pending_ui e serão aplicados
        pelo timer _flush_ui() na thread principal.
        """
        data = self._read_status()
        state   = data.get("state", "idle")
        message = data.get("message", "")
        updated = data.get("updated_at", "")
        metrics = data.get("metrics", {})

        # Não recalcula se nada mudou — mas durante sync sempre relê o progresso
        if updated == self._last_updated and state == self._last_state:
            if state != "running":
                return

        self._last_updated = updated
        self._last_state   = state

        # Registra início do sync
        if state == "running" and self._sync_started is None:
            self._sync_started = time.time()
        elif state != "running":
            self._sync_started = None

        criadas     = metrics.get("criadas", 0)
        atualizadas = metrics.get("atualizadas", 0)
        erros_fin   = metrics.get("erros", 0)
        total_new   = criadas + atualizadas

        # Calcula novo título da menu bar
        if state == "running":
            prog = self._read_progress()
            if prog and prog.get("total", 0) > 0:
                cur   = prog["current"]
                tot   = prog["total"]
                erros = prog.get("erros", 0)
                pct = int(cur / tot * 100)
                new_title = f"⟳ {pct}% ✕{erros}" if erros else f"⟳ {pct}%"
            else:
                new_title = "⟳ …"
        elif state == "ok":
            if erros_fin:
                new_title = f"✓ {total_new} ✕{erros_fin}"
            elif total_new > 0:
                new_title = f"✓ {total_new}"
            else:
                new_title = "✓"
        elif state == "error":
            new_title = "✕"
        else:
            new_title = ICON.get(state, "·")

        # Calcula texto do item de status
        if state == "running":
            status_text = f"⟳  {message or 'Sincronizando…'}"
        elif state == "ok":
            elapsed = metrics.get("elapsed_s", 0)
            elapsed_str = f"  ({elapsed:.0f}s)" if elapsed else ""
            status_text = f"✓  {message or 'Atualizado'}{elapsed_str}"
        elif state == "error":
            status_text = f"✕  {message or 'Erro no pipeline'}"
        else:
            status_text = "Aguardando sync…"

        # Calcula texto da última sincronização
        last_sync_text = None
        if updated:
            try:
                dt  = datetime.fromisoformat(updated)
                rel = self._relative_time(dt)
                last_sync_text = f"   último sync: {rel}"
            except Exception:
                last_sync_text = f"   {updated[:16]}"

        # Armazena resultado para a thread principal aplicar
        self._pending_ui = {
            "title":          new_title,
            "status_text":    status_text,
            "last_sync_text": last_sync_text,
            "is_running":     (state == "running"),
        }

    @rumps.timer(1)
    def _flush_ui(self, _):
        """
        Roda na thread principal (garantido pelo rumps.timer).
        Aplica qualquer atualização pendente calculada pela thread de background.
        """
        pending = getattr(self, "_pending_ui", None)
        if not pending:
            return
        self._pending_ui = None

        self.title = pending["title"]
        self.status_item.title = pending["status_text"]
        if pending["last_sync_text"]:
            self.last_sync_item.title = pending["last_sync_text"]

        is_running = pending["is_running"]
        self.sync_now.set_callback(None if is_running else self.run_sync)
        self.full_sync.set_callback(None if is_running else self.run_full_sync)
        self.dry_run_item.set_callback(None if is_running else self.run_dry_run)

    def _read_progress(self) -> dict:
        try:
            p = Path(PROGRESS_FILE)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _read_status(self) -> dict:
        try:
            p = Path(STATUS_FILE)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _relative_time(self, dt: datetime) -> str:
        # Normaliza para naive (remove tzinfo) para evitar TypeError ao subtrair
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        delta = datetime.now() - dt
        s = int(delta.total_seconds())
        if s < 0:       return "agora mesmo"   # relógio ligeiramente fora de sync
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
                self._proc = subprocess.Popen(cmd)
                self._proc.wait()
            except Exception as e:
                rumps.notification("VaultAI", "Erro", str(e))
            finally:
                self._proc = None
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
        vault = os.path.expanduser("~/VaultAI")
        subprocess.Popen(["open", vault])

    def _open_in_terminal(self, path: str):
        Path(path).touch(exist_ok=True)  # garante que o arquivo existe antes de abrir
        subprocess.Popen(["open", "-a", "Xcode", path])

    # ── Controle dos LaunchAgents ──────────────────────────────────────────────

    def _launchctl(self, *args) -> bool:
        try:
            r = subprocess.run(["launchctl", *args],
                               capture_output=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def _agent_loaded(self, label: str) -> bool:
        r = subprocess.run(["launchctl", "list", label],
                           capture_output=True, timeout=10)
        return r.returncode == 0

    def _plist_exists(self, path: str) -> bool:
        return Path(path).exists()

    def _write_pipeline_plist(self):
        python  = sys.executable
        script  = os.path.join(SCRIPTS_DIR, "pipeline.py")
        log_out = os.path.expanduser("~/.vault/launchd.log")
        Path(AGENT_PLIST).parent.mkdir(parents=True, exist_ok=True)
        Path(AGENT_PLIST).write_text(textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
              "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>          <string>com.vaultai.pipeline</string>
                <key>ProgramArguments</key>
                <array>
                    <string>{python}</string>
                    <string>{script}</string>
                </array>
                <key>StartInterval</key>  <integer>{PIPELINE_INTERVAL_SECS}</integer>
                <key>RunAtLoad</key>      <false/>
                <key>StandardOutPath</key><string>{log_out}</string>
                <key>StandardErrorPath</key><string>{log_out}</string>
            </dict>
            </plist>
        """), encoding="utf-8")

    def _write_menubar_plist(self):
        python = sys.executable
        script = os.path.abspath(__file__)
        log_out = os.path.expanduser("~/.vault/menubar.log")
        Path(MENUBAR_PLIST).parent.mkdir(parents=True, exist_ok=True)
        Path(MENUBAR_PLIST).write_text(textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
              "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>             <string>com.vaultai.menubar</string>
                <key>ProgramArguments</key>
                <array>
                    <string>{python}</string>
                    <string>{script}</string>
                </array>
                <key>RunAtLoad</key>         <false/>
                <key>KeepAlive</key>         <false/>
                <key>StandardOutPath</key>   <string>{log_out}</string>
                <key>StandardErrorPath</key> <string>{log_out}</string>
            </dict>
            </plist>
        """), encoding="utf-8")

    def _refresh_toggles(self):
        sync_on = self._agent_loaded("com.vaultai.pipeline")
        self.toggle_sync.title = "⏸ Pausar sync automático" if sync_on else "▶ Retomar sync automático"

        login_on = self._plist_exists(MENUBAR_PLIST) and self._agent_loaded("com.vaultai.menubar")
        self.toggle_login.title = "✕ Não iniciar com o sistema" if login_on else "⌂ Iniciar com o sistema"

    def toggle_sync_cb(self, _):
        sync_on = self._agent_loaded("com.vaultai.pipeline")
        if sync_on:
            self._launchctl("unload", AGENT_PLIST)
        else:
            if not self._plist_exists(AGENT_PLIST):
                self._write_pipeline_plist()
            self._launchctl("load", AGENT_PLIST)
        self._refresh_toggles()

    def toggle_login_cb(self, _):
        login_on = self._plist_exists(MENUBAR_PLIST) and self._agent_loaded("com.vaultai.menubar")
        if login_on:
            self._launchctl("unload", MENUBAR_PLIST)
            try:
                Path(MENUBAR_PLIST).unlink()
            except Exception:
                pass
        else:
            self._write_menubar_plist()
            self._launchctl("load", MENUBAR_PLIST)
        self._refresh_toggles()

    def quit_app(self, _):
        # 1. Encerra o sync que estiver rodando agora (se houver)
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass

        # 2. Descarrega o LaunchAgent do pipeline para interromper o ciclo
        #    de 30 minutos enquanto o menu bar estiver fechado.
        #    O agente é recarregado automaticamente quando o menu bar abrir.
        if self._agent_loaded("com.vaultai.pipeline"):
            self._launchctl("unload", AGENT_PLIST)

        rumps.quit_application()

    # ── Timer para forçar refresh do progresso durante sync ───────────────

    @rumps.timer(2)
    def poll_progress(self, _):
        """Durante sync, força recálculo a cada 2s. A aplicação na UI ocorre via _flush_ui."""
        if self._last_state == "running":
            self._compute_status()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Verifica dependência
    try:
        import rumps  # noqa
    except ImportError:
        print("Instale rumps: pip install rumps")
        raise

    VaultMenuBar().run()
