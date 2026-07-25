#!/usr/bin/env python3
"""
vault_menubar.py — VaultAI menu bar app
Requer: pip install rumps

Ícone fixo de cubo/BD na menu bar; estado detalhado no menu dropdown.
"""

import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import rumps
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import (
        STATUS_FILE, SCRIPTS_DIR, PIPELINE_LOG as LOG_FILE,
        SYNC_LOG, POLL_SECS, VAULT_PATH, PYTHON_BIN,
        AGENT_PLIST, MENUBAR_PLIST, PIPELINE_INTERVAL_SECS,
        PIPELINE_LABEL, MENUBAR_LABEL, LEGACY_MENUBAR_LABEL,
        PROGRESS_FILE, SYNC_PAUSED_FILE, LOGIN_DISABLED_FILE, LAUNCHER_PATH,
        MENUBAR_ICON_PATH, STATE_DIR, LOCK_FILE,
    )
except ModuleNotFoundError:
    _alert = (
        'display alert "VaultAI — configuração ausente" '
        'message "config.py não encontrado. No diretório do projeto, rode:\\n\\n'
        'cp config.example.py config.py" as critical'
    )
    subprocess.run(["osascript", "-e", _alert])
    sys.exit(1)

from utils import load_preferences, save_preference

# Overlay de preferências editáveis pela UI (~/.vault/preferences.json)
# sobrepõe valores de config.py sem precisar reescrever o módulo.
_prefs = load_preferences(STATE_DIR)
VAULT_PATH = _prefs.get("vault_path", VAULT_PATH)
PIPELINE_INTERVAL_SECS = _prefs.get("pipeline_interval_secs", PIPELINE_INTERVAL_SECS)

MENUBAR_SCRIPT = os.path.join(SCRIPTS_DIR, "vault_menubar.py")

PIPELINE = os.path.join(SCRIPTS_DIR, "pipeline.py")

STATUS_ICON = {
    "idle":    "○",
    "running": "◐",
    "ok":      "●",
    "error":   "✕",
}

SYNC_INTERVAL_MIN = PIPELINE_INTERVAL_SECS // 60

# Sons
SOUND_OK    = "Glass"
SOUND_ERROR = "Basso"


def _section(title: str) -> rumps.MenuItem:
    item = rumps.MenuItem(title, callback=None)
    return item


def _progress_bar(pct: int, width: int = 14) -> str:
    pct = max(0, min(100, pct))
    filled = int(pct / 100 * width)
    return f"{'█' * filled}{'░' * (width - filled)}  {pct}%"


def _sync_toggle_title(on: bool) -> str:
    status = "Ativado" if on else "Desativado"
    return f"Sync automático ({SYNC_INTERVAL_MIN} min) — {status}"


def ensure_launcher() -> str:
    """Cria VaultAI.app em ~/Applications para reabrir o menu bar."""
    python = PYTHON_BIN if os.path.isfile(PYTHON_BIN) else sys.executable
    log_path = os.path.expanduser("~/.vault/menubar.log")
    app_path = Path(LAUNCHER_PATH)
    contents = app_path / "Contents"
    macos_dir = contents / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)

    launcher = macos_dir / "launcher"
    launcher.write_text(
        f"""#!/bin/bash
if pgrep -f "{MENUBAR_SCRIPT}" >/dev/null 2>&1; then
    osascript -e 'display notification "VaultAI já está ativo na barra de menu." with title "VaultAI"'
    exit 0
fi
nohup "{python}" "{MENUBAR_SCRIPT}" >> "{log_path}" 2>&1 &
osascript -e 'display notification "VaultAI iniciado na barra de menu." with title "VaultAI"'
exit 0
""",
        encoding="utf-8",
    )
    os.chmod(launcher, 0o755)

    (contents / "Info.plist").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>pt-BR</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>com.vaultai.launcher</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>VaultAI</string>
    <key>CFBundleDisplayName</key>
    <string>VaultAI</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
""",
        encoding="utf-8",
    )

    legacy = Path(os.path.expanduser("~/Applications/VaultAI.command"))
    if legacy.exists():
        legacy.unlink()

    return str(app_path)


def _format_metrics(criadas: int, atualizadas: int, erros: int) -> str:
    parts = []
    if criadas:
        parts.append(f"{criadas} nova{'s' if criadas != 1 else ''}")
    if atualizadas:
        parts.append(f"{atualizadas} atualizada{'s' if atualizadas != 1 else ''}")
    if erros:
        parts.append(f"{erros} erro{'s' if erros != 1 else ''}")
    return " · ".join(parts) if parts else "Nenhuma alteração"


class VaultMenuBar(rumps.App):

    def __init__(self):
        super().__init__(
            name="VaultAI",
            title=None,
            icon=MENUBAR_ICON_PATH if os.path.isfile(MENUBAR_ICON_PATH) else None,
            template=True,
            quit_button=None,   # customizamos o quit abaixo
        )

        # ── Painel de status ───────────────────────────────────────────────
        self.header_item    = _section("VaultAI")
        self.status_item    = _section(f"{STATUS_ICON['idle']}  Aguardando…")
        self.metrics_item   = _section("")
        self.progress_item  = _section("")
        self.last_sync_item = _section("")
        self.schedule_item  = _section("")

        self.metrics_item.hidden = True
        self.progress_item.hidden = True
        self.last_sync_item.hidden = True

        # ── Ações ──────────────────────────────────────────────────────────
        self.sync_now     = rumps.MenuItem("Agora",              callback=self.run_sync)
        self.full_sync    = rumps.MenuItem("Completo",           callback=self.run_full_sync)
        self.dry_run_item = rumps.MenuItem("Simular (dry run)",  callback=self.run_dry_run)
        self.folder_sync  = rumps.MenuItem("Pasta específica…",  callback=self.run_folder_sync)
        self.cancel_sync  = rumps.MenuItem("Cancelar",           callback=None)
        self.sync_menu    = rumps.MenuItem("Sincronizar")
        self.sync_menu.update([
            self.sync_now, self.full_sync, self.dry_run_item, self.folder_sync,
            rumps.separator,
            self.cancel_sync,
        ])

        self.open_vault    = rumps.MenuItem("Vault no Finder",   callback=self.open_vault_cb)
        self.open_log      = rumps.MenuItem("Log do pipeline",   callback=self.open_pipeline_log)
        self.open_sync_log = rumps.MenuItem("Log do sync",       callback=self.open_sync_log_cb)
        self.open_menu     = rumps.MenuItem("Abrir")
        self.open_menu.update([self.open_vault, self.open_log, self.open_sync_log])

        # ── Configurações ──────────────────────────────────────────────────
        self.toggle_sync  = rumps.MenuItem(
            _sync_toggle_title(on=True),
            callback=self.toggle_sync_cb,
        )
        self.toggle_login = rumps.MenuItem(
            "Iniciar com o sistema — Ativado",
            callback=self.toggle_login_cb,
        )
        self.open_launcher = rumps.MenuItem(
            "Atalho para reabrir o app",
            callback=self.open_launcher_cb,
        )

        # ── Preferências ──────────────────────────────────────────────────
        self.edit_vault_path    = rumps.MenuItem("Vault Path…",        callback=self.edit_vault_path_cb)
        self.edit_sync_interval = rumps.MenuItem("Intervalo de sync…", callback=self.edit_sync_interval_cb)
        self.prefs_menu = rumps.MenuItem("Preferências")
        self.prefs_menu.update([self.edit_vault_path, self.edit_sync_interval])

        # ── Manutenção ────────────────────────────────────────────────────
        self.release_lock_item = rumps.MenuItem(
            "Liberar lock travado", callback=self.release_lock_cb,
        )

        self.quit_item = rumps.MenuItem("Sair", callback=self.quit_app)

        self.menu = [
            self.header_item,
            _section("— Status —"),
            self.status_item,
            self.metrics_item,
            self.progress_item,
            self.last_sync_item,
            self.schedule_item,
            rumps.separator,
            self.sync_menu,
            self.open_menu,
            rumps.separator,
            _section("— Configurações —"),
            self.toggle_sync,
            self.toggle_login,
            self.open_launcher,
            self.prefs_menu,
            rumps.separator,
            _section("— Manutenção —"),
            self.release_lock_item,
            rumps.separator,
            self.quit_item,
        ]

        ensure_launcher()

        # Atualiza labels dos toggles com o estado real
        self._refresh_toggles()

        # Respeita preferências persistidas de sync e login.
        self._apply_sync_preference()
        self._apply_login_preference()

        # Aviso único: pasta do vault ainda não existe (será criada no 1º sync)
        if not Path(os.path.expanduser(VAULT_PATH)).is_dir():
            rumps.notification(
                "VaultAI", "Vault ainda não existe",
                f"'{VAULT_PATH}' será criado automaticamente no primeiro sync.",
            )

        # Estado interno
        self._last_state    = "idle"
        self._running       = False
        self._last_updated  = None
        self._last_ui       = None   # última UI totalmente calculada (p/ countdown)
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

        schedule_text = self._schedule_label(updated, state)

        # Não recalcula se nada mudou — mas a contagem regressiva precisa
        # continuar avançando mesmo parado, e o progresso sempre relê durante sync.
        if updated == self._last_updated and state == self._last_state:
            if state != "running":
                if self._last_ui is not None:
                    self._pending_ui = {**self._last_ui, "schedule_text": schedule_text}
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
        # Calcula texto do item de status (resumo) e métricas (detalhe)
        icon = STATUS_ICON.get(state, STATUS_ICON["idle"])
        if state == "running":
            status_text = f"{icon}  {message or 'Sincronizando…'}"
        elif state == "ok":
            status_text = f"{icon}  Atualizado"
        elif state == "error":
            status_text = f"{icon}  {message or 'Erro no pipeline'}"
        else:
            status_text = f"{icon}  Aguardando sync…"

        metrics_text = None
        show_metrics = False
        if state in ("ok", "error") and (criadas or atualizadas or erros_fin):
            metrics_text = _format_metrics(criadas, atualizadas, erros_fin)
            show_metrics = bool(metrics_text)

        progress_text = None
        show_progress = False
        if state == "running":
            prog = self._read_progress()
            if prog and prog.get("total", 0) > 0:
                cur = prog["current"]
                tot = prog["total"]
                pct = int(cur / tot * 100)
                progress_text = _progress_bar(pct)
                show_progress = True

        # Calcula texto da última sincronização
        last_sync_text = None
        show_last_sync = False
        if updated:
            try:
                dt  = datetime.fromisoformat(updated)
                rel = self._relative_time(dt)
                elapsed = metrics.get("elapsed_s", 0)
                elapsed_str = f" · {elapsed:.0f}s" if elapsed and state == "ok" else ""
                last_sync_text = f"◷  Último sync {rel}{elapsed_str}"
                show_last_sync = True
            except Exception:
                last_sync_text = f"◷  {updated[:16]}"
                show_last_sync = True

        # Armazena resultado para a thread principal aplicar
        self._pending_ui = {
            "status_text":    status_text,
            "status_icon":    icon,
            "metrics_text":   metrics_text,
            "show_metrics":   show_metrics and bool(metrics_text),
            "progress_text":  progress_text,
            "show_progress":  show_progress,
            "last_sync_text": last_sync_text,
            "show_last_sync": show_last_sync,
            "schedule_text":  schedule_text,
            "is_running":     (state == "running"),
        }
        self._last_ui = self._pending_ui

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

        self.status_item.title = pending["status_text"]
        if pending.get("status_icon"):
            self.title = pending["status_icon"]   # visível na barra sem abrir o dropdown

        self.metrics_item.title = pending["metrics_text"] or ""
        self.metrics_item.hidden = not pending["show_metrics"]

        self.progress_item.title = pending["progress_text"] or ""
        self.progress_item.hidden = not pending["show_progress"]

        if pending["last_sync_text"]:
            self.last_sync_item.title = pending["last_sync_text"]
        self.last_sync_item.hidden = not pending["show_last_sync"]

        self.schedule_item.title = pending["schedule_text"]

        is_running = pending["is_running"]
        self.sync_now.set_callback(None if is_running else self.run_sync)
        self.full_sync.set_callback(None if is_running else self.run_full_sync)
        self.dry_run_item.set_callback(None if is_running else self.run_dry_run)
        self.folder_sync.set_callback(None if is_running else self.run_folder_sync)
        self.cancel_sync.set_callback(self.cancel_sync_cb if is_running else None)

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
        self.status_item.title = f"{STATUS_ICON['running']}  {label}…"
        self.progress_item.hidden = True
        self.metrics_item.hidden = True

        def worker():
            try:
                python = PYTHON_BIN if os.path.isfile(PYTHON_BIN) else sys.executable
                cmd = [python, PIPELINE] + extra_args
                # Grupo de processos próprio: permite matar o pipeline.py e os
                # subprocessos que ele dispara (notes_to_obsidian/organize_vault
                # e o osascript deles) de uma vez, ao cancelar.
                self._proc = subprocess.Popen(cmd, start_new_session=True)
                self._proc.wait()
            except Exception as e:
                rumps.notification("VaultAI", "Erro", str(e))
            finally:
                self._proc = None
                self._running = False
                self._last_updated = None  # força refresh

        threading.Thread(target=worker, daemon=True).start()

    def run_sync(self, _=None):
        self._run_pipeline([], "Sincronizando")

    def run_full_sync(self, _):
        self._run_pipeline(["--full"], "Sync completo")

    def run_dry_run(self, _):
        self._run_pipeline(["--dry-run"], "Simulando")

    def run_folder_sync(self, _):
        if self._running:
            rumps.notification("VaultAI", "Pipeline em execução",
                               "Aguarde o sync atual terminar.")
            return
        response = rumps.Window(
            message="Nome exato da pasta (como aparece no Apple Notes):",
            title="Sincronizar pasta específica",
            default_text="",
            ok="Sincronizar",
            cancel="Cancelar",
            dimensions=(300, 20),
        ).run()
        if not response.clicked:
            return
        name = response.text.strip()
        if not name:
            return
        self._run_pipeline(["--folder", name], f"Sincronizando '{name}'")

    def cancel_sync_cb(self, _):
        proc = self._proc
        if proc is None:
            rumps.notification("VaultAI", "Cancelar", "Nenhum sync em execução.")
            return
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
                proc.wait(timeout=5)
        except Exception as e:
            self._log_launchctl(f"cancelar sync -> exception: {e}")
        finally:
            # SIGTERM não garante que o finally do pipeline.py rode — limpa
            # lock/progresso aqui pra não deixar estado travado.
            Path(LOCK_FILE).unlink(missing_ok=True)
            Path(PROGRESS_FILE).unlink(missing_ok=True)
            self._proc = None
            self._running = False
            self._last_updated = None
            self.status_item.title = f"{STATUS_ICON['idle']}  Cancelado"
            self.progress_item.hidden = True
        rumps.notification("VaultAI", "Sync cancelado", "")

    # ── Ações de log / vault ───────────────────────────────────────────────

    def open_pipeline_log(self, _):
        self._open_in_terminal(LOG_FILE)

    def open_sync_log_cb(self, _):
        self._open_in_terminal(SYNC_LOG)

    def open_vault_cb(self, _):
        subprocess.Popen(["open", os.path.expanduser(VAULT_PATH)])

    def _open_in_terminal(self, path: str):
        Path(path).touch(exist_ok=True)
        subprocess.Popen(["open", "-a", "TextEdit", path])

    # ── Controle dos LaunchAgents ──────────────────────────────────────────────

    def _launch_domain(self) -> str:
        return f"gui/{os.getuid()}"

    def _log_launchctl(self, message: str):
        try:
            log_path = os.path.expanduser("~/.vault/menubar.log")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"[{ts}] {message}\n")
        except Exception:
            pass

    def _launchctl_run(self, *args) -> subprocess.CompletedProcess | None:
        try:
            return subprocess.run(
                ["/bin/launchctl", *args],
                capture_output=True, text=True, timeout=10,
            )
        except Exception as exc:
            self._log_launchctl(f"launchctl {' '.join(args)} -> exception: {exc}")
            return None

    def _sync_paused(self) -> bool:
        return Path(SYNC_PAUSED_FILE).exists()

    def _set_sync_paused(self, paused: bool):
        path = Path(SYNC_PAUSED_FILE)
        if paused:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        else:
            path.unlink(missing_ok=True)

    def _login_disabled(self) -> bool:
        return Path(LOGIN_DISABLED_FILE).exists()

    def _set_login_disabled(self, disabled: bool):
        path = Path(LOGIN_DISABLED_FILE)
        if disabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        else:
            path.unlink(missing_ok=True)

    def _menubar_running(self) -> bool:
        try:
            result = subprocess.run(
                ["/usr/bin/pgrep", "-f", MENUBAR_SCRIPT],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def _launchctl_disable(self, label: str) -> bool:
        result = self._launchctl_run("disable", f"{self._launch_domain()}/{label}")
        return bool(result and result.returncode == 0)

    def _launchctl_enable(self, label: str) -> bool:
        result = self._launchctl_run("enable", f"{self._launch_domain()}/{label}")
        return bool(result and result.returncode == 0)

    def _agent_loaded(self, label: str) -> bool:
        domain = self._launch_domain()
        for args in (
            ("print", f"{domain}/{label}"),
            ("list", label),
        ):
            result = self._launchctl_run(*args)
            if result and result.returncode == 0:
                return True
        return False

    def _launchctl_load(self, plist: str) -> bool:
        label = Path(plist).stem
        if self._agent_loaded(label):
            return True

        domain = self._launch_domain()
        self._launchctl_run("bootout", domain, label)
        self._launchctl_run("unload", plist)

        for args in (("bootstrap", domain, plist), ("load", plist)):
            result = self._launchctl_run(*args)
            if result and result.returncode == 0 and self._agent_loaded(label):
                return True
            if result and result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                self._log_launchctl(f"launchctl {' '.join(args)} -> {err}")

        loaded = self._agent_loaded(label)
        if not loaded:
            self._log_launchctl(f"falha ao carregar {label}")
        return loaded

    def _launchctl_unload(self, plist: str, label: str) -> bool:
        if not self._agent_loaded(label):
            return True

        domain = self._launch_domain()
        for args in (("bootout", domain, label), ("bootout", domain, plist), ("unload", plist)):
            result = self._launchctl_run(*args)
            if result and result.returncode == 0 and not self._agent_loaded(label):
                return True
            if result and result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                self._log_launchctl(f"launchctl {' '.join(args)} -> {err}")

        unloaded = not self._agent_loaded(label)
        if not unloaded:
            self._log_launchctl(f"falha ao descarregar {label}")
        return unloaded

    def _apply_sync_preference(self):
        if self._sync_paused():
            self._launchctl_unload(AGENT_PLIST, PIPELINE_LABEL)
            return
        if self._plist_exists(AGENT_PLIST):
            self._launchctl_load(AGENT_PLIST)

    def _apply_login_preference(self):
        if self._login_disabled():
            self._launchctl_disable(MENUBAR_LABEL)
        else:
            self._launchctl_enable(MENUBAR_LABEL)

    def _plist_exists(self, path: str) -> bool:
        return Path(path).exists()

    def _python_for_plist(self) -> str:
        if os.path.isfile(PYTHON_BIN):
            return PYTHON_BIN
        return sys.executable

    def _write_pipeline_plist(self):
        python  = self._python_for_plist()
        script  = os.path.join(SCRIPTS_DIR, "pipeline.py")
        log_out = os.path.expanduser("~/.vault/launchd.log")
        Path(AGENT_PLIST).parent.mkdir(parents=True, exist_ok=True)
        Path(AGENT_PLIST).write_text(textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
              "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>          <string>{PIPELINE_LABEL}</string>
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
        python = self._python_for_plist()
        script = os.path.join(SCRIPTS_DIR, "vault_menubar.py")
        log_out = os.path.expanduser("~/.vault/menubar.log")
        Path(MENUBAR_PLIST).parent.mkdir(parents=True, exist_ok=True)
        Path(MENUBAR_PLIST).write_text(textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
              "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>             <string>{MENUBAR_LABEL}</string>
                <key>ProgramArguments</key>
                <array>
                    <string>{python}</string>
                    <string>{script}</string>
                </array>
                <key>RunAtLoad</key>         <true/>
                <key>KeepAlive</key>
                <dict>
                    <key>SuccessfulExit</key>
                    <false/>
                </dict>
                <key>StandardOutPath</key>   <string>{log_out}</string>
                <key>StandardErrorPath</key> <string>{log_out}</string>
            </dict>
            </plist>
        """), encoding="utf-8")

    def _schedule_label(self, updated: str = "", state: str = "") -> str:
        if self._sync_paused():
            return "○  Automático: desativado"
        label = f"●  Automático: ativado · a cada {SYNC_INTERVAL_MIN} min"
        if state != "running" and updated:
            try:
                dt = datetime.fromisoformat(updated)
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                remaining = (dt + timedelta(seconds=PIPELINE_INTERVAL_SECS) - datetime.now()).total_seconds()
                if remaining > 0:
                    label += f"  ·  próximo em ~{max(1, int(remaining // 60))} min"
                else:
                    label += "  ·  próximo em breve"
            except Exception:
                pass
        return label

    def _refresh_toggles(self):
        sync_on = not self._sync_paused()
        self.toggle_sync.state = 1 if sync_on else 0
        self.toggle_sync.title = _sync_toggle_title(sync_on)

        login_on = not self._login_disabled()
        self.toggle_login.state = 1 if login_on else 0
        self.toggle_login.title = (
            "Iniciar com o sistema — Ativado" if login_on
            else "Iniciar com o sistema — Desativado"
        )
        self.open_launcher.title = "Abrir atalho em Aplicações (VaultAI)"

        self.schedule_item.title = self._schedule_label()

    def toggle_sync_cb(self, _):
        if not self._sync_paused():
            ok = self._launchctl_unload(AGENT_PLIST, PIPELINE_LABEL)
            if ok:
                self._set_sync_paused(True)
                rumps.notification("VaultAI", "Sync automático", "Desativado")
            else:
                rumps.notification(
                    "VaultAI", "Erro",
                    "Não foi possível pausar o sync automático.",
                )
        else:
            if not self._plist_exists(AGENT_PLIST):
                self._write_pipeline_plist()
            ok = self._launchctl_load(AGENT_PLIST)
            if ok:
                self._set_sync_paused(False)
                rumps.notification(
                    "VaultAI", "Sync automático",
                    f"Ativado · a cada {SYNC_INTERVAL_MIN} min",
                )
            else:
                rumps.notification(
                    "VaultAI", "Erro",
                    "Não foi possível retomar o sync automático. "
                    "Veja ~/.vault/menubar.log",
                )
        self._refresh_toggles()
        self._compute_status()

    def open_launcher_cb(self, _):
        ensure_launcher()
        subprocess.Popen(["open", "-R", LAUNCHER_PATH])

    def toggle_login_cb(self, _):
        if not self._login_disabled():
            ensure_launcher()
            rumps.alert(
                title="VaultAI",
                message=(
                    "O ícone será removido da barra de menu.\n\n"
                    f"Para reabrir depois, clique duas vezes em:\n"
                    f"Aplicações → VaultAI.app"
                ),
                ok="Entendi",
            )
            self._set_login_disabled(True)
            self._launchctl_disable(MENUBAR_LABEL)
            self._launchctl_unload(MENUBAR_PLIST, MENUBAR_LABEL)
            rumps.quit_application()
            return

        if not self._plist_exists(MENUBAR_PLIST):
            self._write_menubar_plist()
        self._set_login_disabled(False)
        self._launchctl_enable(MENUBAR_LABEL)
        if not self._menubar_running():
            ok = self._launchctl_load(MENUBAR_PLIST)
        else:
            ok = True
        if ok:
            rumps.notification(
                "VaultAI", "Iniciar com o sistema",
                "Ativado · o app abrirá ao fazer login",
            )
        else:
            self._set_login_disabled(True)
            rumps.notification(
                "VaultAI", "Erro",
                "Não foi possível ativar o início automático.",
            )
        self._refresh_toggles()
        self._compute_status()

    def edit_vault_path_cb(self, _):
        global VAULT_PATH
        response = rumps.Window(
            message="Caminho da pasta do vault Obsidian:",
            title="Vault Path",
            default_text=VAULT_PATH,
            ok="Salvar",
            cancel="Cancelar",
            dimensions=(320, 20),
        ).run()
        if not response.clicked:
            return
        new_path = response.text.strip()
        if not new_path:
            return
        save_preference(STATE_DIR, "vault_path", new_path)
        VAULT_PATH = new_path
        rumps.notification("VaultAI", "Vault Path atualizado", new_path)

    def edit_sync_interval_cb(self, _):
        global PIPELINE_INTERVAL_SECS, SYNC_INTERVAL_MIN
        response = rumps.Window(
            message="Intervalo do sync automático, em minutos:",
            title="Intervalo de sync",
            default_text=str(SYNC_INTERVAL_MIN),
            ok="Salvar",
            cancel="Cancelar",
            dimensions=(200, 20),
        ).run()
        if not response.clicked:
            return
        text = response.text.strip()
        if not text.isdigit() or int(text) <= 0:
            rumps.notification(
                "VaultAI", "Intervalo inválido",
                "Informe um número inteiro de minutos maior que zero.",
            )
            return
        minutes = int(text)
        PIPELINE_INTERVAL_SECS = minutes * 60
        SYNC_INTERVAL_MIN = minutes
        save_preference(STATE_DIR, "pipeline_interval_secs", PIPELINE_INTERVAL_SECS)
        self._refresh_toggles()

        # Se o agente automático já está carregado, reescreve e recarrega
        # o plist pra aplicar o novo intervalo sem precisar reiniciar o app.
        if self._plist_exists(AGENT_PLIST) and not self._sync_paused():
            self._launchctl_unload(AGENT_PLIST, PIPELINE_LABEL)
            self._write_pipeline_plist()
            self._launchctl_load(AGENT_PLIST)

        rumps.notification("VaultAI", "Intervalo de sync atualizado", f"A cada {minutes} min")

    def release_lock_cb(self, _):
        lock = Path(LOCK_FILE)
        if not lock.exists():
            rumps.notification("VaultAI", "Liberar lock", "Nenhum lock ativo no momento.")
            return
        try:
            age = time.time() - lock.stat().st_mtime
        except Exception:
            age = 0
        lock.unlink(missing_ok=True)
        rumps.notification(
            "VaultAI", "Lock liberado",
            f"Lock removido (estava ativo há {age:.0f}s).",
        )

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
