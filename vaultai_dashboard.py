#!/usr/bin/env python3
"""Janela única do VaultAI.

Lê status.json, progress.json, metrics.json e organize_metrics.json.
O .app é gerado por ensure_app(); esta é a única fonte da janela.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
from pathlib import Path

BUNDLE_ID = "com.vaultai.app"
BG = "#1c1c1e"
FG = "#f2f2f7"
CARD = "#2c2c2e"
MUTED = "#9aa3b2"
WINDOW_SIZE = "420x560"
TRACK = "#3a3a3c"
ACCENT = "#5b8def"
BAR_W = 348
BAR_H = 8
METRIC_COLORS = {
    "criadas": "#3ddc97",
    "atualizadas": "#5b8def",
    "erros": "#e85d5d",
    "bloqueadas": "#e6a23c",
}

STATE_COLORS = {
    "ok": "#3ddc97",
    "sincronizando": "#5b8def",
    "pausa": "#e6a23c",
    "erro": "#e85d5d",
    "idle": "#8e8e93",
}

_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>pt-BR</string>
    <key>CFBundleExecutable</key>
    <string>VaultAI</string>
    <key>CFBundleIdentifier</key>
    <string>{bundle_id}</string>
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
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
"""


def state_color(name: str) -> str:
    return STATE_COLORS.get(name, STATE_COLORS["idle"])


def display_state(status: dict | None, paused: bool) -> str:
    raw = (status or {}).get("state") or "idle"
    if raw == "running":
        return "sincronizando"
    if raw == "error":
        return "erro"
    if paused:
        return "pausa"
    if raw == "ok":
        return "ok"
    return "idle"


def _read_json(path: Path) -> dict:
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def read_snapshot(state_dir) -> dict:
    root = Path(state_dir)
    return {
        "status": _read_json(root / "status.json"),
        "metrics": _read_json(root / "metrics.json"),
        "progress": _read_json(root / "progress.json"),
        "organize": _read_json(root / "organize_metrics.json"),
        "paused": (root / "sync_paused").exists(),
    }


def format_sync_line(metrics: dict | None) -> str:
    metrics = metrics or {}
    skipped = "sim" if metrics.get("skipped") else "não"
    return (
        f"criadas: {metrics.get('criadas', 0)} · "
        f"atualizadas: {metrics.get('atualizadas', 0)} · "
        f"erros: {metrics.get('erros', 0)} · "
        f"bloqueadas: {metrics.get('bloqueadas', 0)} · "
        f"skipped: {skipped}"
    )


def format_organize_line(organize: dict | None) -> str:
    organize = organize or {}
    return (
        f"organize: {organize.get('linkadas', 0)} linkadas · "
        f"{organize.get('mocs', 0)} MOC · "
        f"{organize.get('lixo', 0)} lixo"
    )


def format_progress_line(progress: dict | None) -> str | None:
    if not progress:
        return None
    total = progress.get("total") or 0
    if total <= 0:
        return None
    current = progress.get("current") or 0
    return f"progresso: {current}/{total}"


def progress_percent(progress: dict | None) -> int | None:
    if not progress:
        return None
    total = progress.get("total") or 0
    if total <= 0:
        return None
    current = progress.get("current") or 0
    pct = int(current / total * 100)
    return max(0, min(100, pct))


def activity_line(state: str, message: str, progress: dict | None) -> str:
    """Frase curta do estágio atual. Porcentagem só quando há total."""
    text = message or ""
    lowered = text.lower()
    if "organiz" in lowered:
        stage = "Organizando"
    elif "notes" in lowered or "sincron" in lowered:
        stage = "Notas"
    else:
        stage = ""
    pct = progress_percent(progress)
    if state == "sincronizando" and pct is not None:
        name = stage or "Sync"
        return f"{name} · {pct}%"
    if state == "sincronizando":
        return stage or "Preparando o sync…"
    if state == "pausa":
        return "Sync automático pausado"
    if state == "erro":
        return text or "Sync falhou"
    if state == "ok":
        if pct is not None and pct < 100:
            return f"Parcial · {pct}%"
        return "Vault atualizado"
    return "Aguardando o próximo sync"


def expand_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def open_log(path: str, opener=None):
    expanded = expand_path(path)
    run = opener or subprocess.Popen
    run(["open", "-a", "TextEdit", expanded])
    return expanded


def open_vault(path: str, opener=None) -> str:
    expanded = expand_path(path)
    run = opener or subprocess.Popen
    run(["open", expanded])
    return expanded


_SF_DATALESS = 0x40000000
_DATALESS_ERRNO = 11  # EDEADLK ao ler placeholder iCloud
_WINDOW_PYTHON = "/usr/bin/python3"


def _xattr_names(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    try:
        completed = subprocess.run(
            ["xattr", path],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    text = completed.stdout.decode("utf-8", "replace")
    return {line.strip() for line in text.splitlines() if line.strip()}


def path_on_icloud(path: str) -> bool:
    """Árvore do File Provider. Documents/Desktop sincronizados sobem por ancestral."""
    current = os.path.abspath(os.fspath(path))
    while True:
        if "com.apple.file-provider-domain-id" in _xattr_names(current):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def agent_python(project_dir: str) -> str:
    """Python do LaunchAgent (pipeline e menu bar). rumps não está no python da janela.

    Nunca o .venv dataless do repositório no iCloud, e nunca /usr/bin/python3:
    a janela usa esse; a menu bar precisa de rumps, que mora neste venv.
    """
    candidate = os.path.join(pipeline_venv_dir(project_dir), "bin", "python3")
    if interpreter_ready(candidate) and _imports_site(candidate):
        return candidate
    raise SystemExit(f"venv do pipeline não importa site: {candidate}")


def pipeline_venv_dir(project_dir: str) -> str:
    """Venv do LaunchAgent. No iCloud não fica dentro do repositório."""
    project_dir = os.path.abspath(os.fspath(project_dir))
    if not path_on_icloud(project_dir):
        return os.path.join(project_dir, ".venv")
    outside = os.path.expanduser("~/Library/Application Support/VaultAI/venv")
    if path_on_icloud(outside):
        raise SystemExit("não há destino de venv fora do iCloud")
    return outside


def _flags_dataless(path: str) -> bool:
    try:
        st = os.stat(path, follow_symlinks=True)
    except OSError as exc:
        return exc.errno == _DATALESS_ERRNO
    return bool(getattr(st, "st_flags", 0) & _SF_DATALESS)


def is_dataless(path) -> bool:
    """Placeholder iCloud: isfile é True, o tamanho mente, a leitura morre com errno 11."""
    text = os.fspath(path)
    if _flags_dataless(text):
        return True
    if not os.path.isfile(text):
        return False
    try:
        fd = os.open(text, os.O_RDONLY)
    except OSError as exc:
        return exc.errno == _DATALESS_ERRNO
    os.close(fd)
    return False


def _under_venv(path: str) -> bool:
    return ".venv" in Path(os.fspath(path)).parts


def _venv_root(path: str):
    parts = Path(os.fspath(path)).parts
    if ".venv" not in parts:
        return None
    return str(Path(*parts[: parts.index(".venv") + 1]))


def _venv_has_dataless_package(path: str) -> bool:
    root = _venv_root(path)
    if not root:
        return False
    lib = Path(root) / "lib"
    if not lib.is_dir():
        return _flags_dataless(root)
    for site in lib.glob("python*/site-packages"):
        try:
            children = list(site.iterdir())
        except OSError as exc:
            if exc.errno == _DATALESS_ERRNO:
                return True
            continue
        for child in children:
            if _flags_dataless(str(child)):
                return True
    return False


def interpreter_ready(path) -> bool:
    """Dataless não é executável válido. Não abre o arquivo se o flag já denuncia."""
    text = os.fspath(path) if path else ""
    if not text or not os.path.isfile(text):
        return False
    if is_dataless(text):
        return False
    if _under_venv(text) and _venv_has_dataless_package(text):
        return False
    return True


def _imports_site(path: str) -> bool:
    try:
        completed = subprocess.run(
            [path, "-c", "import site"],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def bundle_python(candidate=None) -> str:
    """Interpreter da janela. Nunca um python debaixo de .venv, nunca dataless."""
    options = []
    if candidate:
        options.append(os.fspath(candidate))
    if sys.executable:
        options.append(sys.executable)
    options.append(_WINDOW_PYTHON)
    seen = set()
    for path in options:
        if not path or path in seen:
            continue
        seen.add(path)
        if _under_venv(path) or not os.path.isfile(path) or is_dataless(path):
            continue
        if _imports_site(path):
            return path
    raise SystemExit("nenhum interpreter importa site fora de .venv")


def run_pipeline() -> int:
    from config_import import require

    scripts_dir, python_bin = require("SCRIPTS_DIR", "PYTHON_BIN")
    python = python_bin if interpreter_ready(python_bin) else sys.executable
    if not interpreter_ready(python):
        python = _WINDOW_PYTHON
    script = os.path.join(scripts_dir, "pipeline.py")
    completed = subprocess.run([python, script], check=False)
    return int(completed.returncode)


class DashboardActions:
    """Ações da janela. O botão chama o hook; não substitui o atributo."""

    def __init__(
        self,
        on_pause=None,
        on_resume=None,
        pipeline_runner=None,
        on_error=None,
        state_dir=None,
        launchctl=None,
    ):
        self.on_pause = self._default_pause if on_pause is None else on_pause
        self.on_resume = self._default_resume if on_resume is None else on_resume
        self.pipeline_runner = pipeline_runner or run_pipeline
        self.on_error = on_error
        self.state_dir = Path(state_dir) if state_dir else None
        self._launchctl = launchctl or subprocess.run

    def pause(self):
        self.on_pause()

    def resume(self):
        self.on_resume()

    def sync_now(self):
        try:
            result = self.pipeline_runner()
        except Exception as exc:
            self._report(str(exc))
            return
        if isinstance(result, int) and result != 0:
            self._report(f"Sync falhou ({result})")

    def _report(self, message: str):
        if self.on_error is not None:
            self.on_error(message)

    def _default_pause(self):
        if self._launchctl_agent("unload"):
            self._set_paused(True)

    def _default_resume(self):
        if self._launchctl_agent("load"):
            self._set_paused(False)

    def _set_paused(self, paused: bool):
        if self.state_dir is None:
            return
        path = self.state_dir / "sync_paused"
        if paused:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        else:
            path.unlink(missing_ok=True)

    def _launchctl_agent(self, verb: str) -> bool:
        plist = _agent_plist()
        if not plist:
            self._report("Não foi possível alterar o sync automático.")
            return False
        try:
            result = self._launchctl(
                ["launchctl", verb, plist],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            self._report(str(exc))
            return False
        if getattr(result, "returncode", None) != 0:
            if verb == "unload":
                self._report("Não foi possível pausar o sync automático.")
            else:
                self._report("Não foi possível retomar o sync automático.")
            return False
        return True


def _agent_plist() -> str:
    try:
        from config_import import require

        (plist,) = require("AGENT_PLIST")
    except SystemExit:
        return ""
    return plist or ""


def ensure_app(app_path=None, python=None, script=None) -> str:
    """Gera VaultAI.app. O executável chama a fonte; não copia o .py."""
    if app_path is None:
        from config_import import require

        (launcher,) = require("LAUNCHER_PATH")
        app_path = launcher
    if python is None:
        try:
            from config_import import require

            (python,) = require("PYTHON_BIN")
        except SystemExit:
            python = None
    python = bundle_python(python)
    app = Path(app_path)
    source = Path(script or Path(__file__).resolve())
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    for leftover in macos.iterdir():
        if leftover.is_file() and leftover.name != "VaultAI":
            leftover.unlink()
    launcher = macos / "VaultAI"
    launcher.write_text(
        "#!/bin/bash\n"
        f"exec {shlex.quote(str(python))} {shlex.quote(str(source))}\n",
        encoding="utf-8",
    )
    os.chmod(launcher, 0o755)
    (app / "Contents" / "Info.plist").write_text(
        _PLIST.format(bundle_id=BUNDLE_ID),
        encoding="utf-8",
    )
    return str(app)


class VaultWindow:
    def __init__(
        self,
        state_dir,
        master=None,
        log_path="~/.vault/pipeline.log",
        vault_path="~",
        on_pause=None,
        on_resume=None,
        opener=None,
        pipeline_runner=None,
    ):
        import tkinter as tk
        import tkinter.font as tkfont

        self._tk = tk
        self.root = master or tk.Tk()
        self.root.title("VaultAI")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(420, 560)
        self.root.maxsize(420, 560)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.state_dir = Path(state_dir)
        self.log_path = log_path
        self.vault_path = vault_path
        self.opener = opener or subprocess.Popen
        self._error = ""
        base = tkfont.nametofont("TkDefaultFont")
        self.font = tkfont.Font(root=self.root, font=base)
        self.font.configure(size=13)
        self.title_font = tkfont.Font(root=self.root, font=base)
        self.title_font.configure(size=20)
        self.caption_font = tkfont.Font(root=self.root, font=base)
        self.caption_font.configure(size=11)
        self.metric_font = tkfont.Font(root=self.root, font=base)
        self.metric_font.configure(size=18)
        self.percent_font = tkfont.Font(root=self.root, font=base)
        self.percent_font.configure(size=15)
        self.actions = DashboardActions(
            on_pause=on_pause,
            on_resume=on_resume,
            pipeline_runner=pipeline_runner,
            on_error=self.show_error,
            state_dir=self.state_dir,
        )
        self._busy = False
        self._animating = False
        self._anim_id = None
        self._build()
        self._show_idle_state()
        self.refresh()

    def _pack(self, widget, **kwargs):
        widget.pack(**kwargs)
        return widget

    def _label(self, parent, text, *, font=None, fg=FG, bg=BG, width=None):
        label = self._tk.Label(
            parent,
            text=text,
            font=font or self.font,
            fg=fg,
            bg=bg,
            anchor="w",
            justify="left",
        )
        if width is not None:
            label.configure(width=width)
        return label

    def _button(self, parent, text, command, *, primary=False):
        bg = ACCENT if primary else CARD
        return self._tk.Button(
            parent,
            text=text,
            command=command,
            font=self.font,
            fg=FG,
            bg=bg,
            activeforeground=FG,
            activebackground="#6f9cf2" if primary else "#3a3a3c",
            highlightthickness=0,
            relief="flat",
            padx=10,
            pady=8 if primary else 6,
            borderwidth=0,
        )

    def _section(self, parent, text):
        return self._label(parent, text, font=self.caption_font, fg=MUTED)

    def _card(self, parent):
        card = self._tk.Frame(parent, bg=CARD)
        self._pack(card, fill="x", pady=(12, 0))
        inner = self._tk.Frame(card, bg=CARD)
        self._pack(inner, fill="x", padx=12, pady=12)
        return inner

    def _metric(self, parent, key, caption):
        tile = self._tk.Frame(parent, bg=CARD)
        self._pack(tile, side="left", expand=True, fill="x")
        value = self._label(
            tile,
            "0",
            font=self.metric_font,
            fg=METRIC_COLORS[key],
            bg=CARD,
        )
        self._pack(value, anchor="w")
        cap = self._label(tile, caption, font=self.caption_font, fg=MUTED, bg=CARD)
        self._pack(cap, anchor="w")
        return value

    def _paint_bar(self, percent, color):
        self._stop_indeterminate()
        canvas = self.bar
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        self._capsule(canvas, 0, 0, width, height, TRACK)
        if not percent:
            return
        fill = max(height, int(width * (percent / 100)))
        self._capsule(canvas, 0, 0, fill, height, color)

    def _paint_indeterminate(self, phase, color):
        canvas = self.bar
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        self._capsule(canvas, 0, 0, width, height, TRACK)
        chunk = 72
        x1 = phase - chunk
        x2 = phase
        if x2 > 0 and x1 < width:
            self._capsule(canvas, max(0, x1), 0, min(width, x2), height, color)

    def _capsule(self, canvas, x1, y1, x2, y2, fill):
        if x2 - x1 < 2:
            return
        radius = max(1, (y2 - y1) // 2)
        canvas.create_oval(x1, y1, x1 + radius * 2, y2, fill=fill, outline=fill)
        canvas.create_oval(x2 - radius * 2, y1, x2, y2, fill=fill, outline="")
        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")

    def _kick_indeterminate(self):
        if self._animating:
            return
        self._animating = True
        self._phase = 0
        self._tick_bar()

    def _tick_bar(self):
        if not self._animating:
            return
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        self._phase = (getattr(self, "_phase", 0) + 14) % (BAR_W + 80)
        self._paint_indeterminate(self._phase, state_color("sincronizando"))
        self._anim_id = self.root.after(40, self._tick_bar)

    def _stop_indeterminate(self):
        self._animating = False
        anim_id = getattr(self, "_anim_id", None)
        if anim_id is not None:
            try:
                self.root.after_cancel(anim_id)
            except Exception:
                pass
            self._anim_id = None

    def _show_starting(self):
        color = state_color("sincronizando")
        self.state_label.configure(text="sincronizando", fg=color)
        self.state_dot.configure(fg=color)
        self.percent_label.configure(text="…", fg=color)
        self.activity_label.configure(text="Iniciando sincronização…")
        self._kick_indeterminate()

    def _build(self):
        outer = self._tk.Frame(self.root, bg=BG)
        self._pack(outer, fill="both", expand=True, padx=18, pady=16)

        # Header: título + estado compacto
        header = self._tk.Frame(outer, bg=BG)
        self._pack(header, fill="x")
        self._pack(
            self._label(header, "VaultAI", font=self.title_font, fg=FG),
            side="left",
        )
        pill = self._tk.Frame(header, bg=CARD)
        self._pack(pill, side="right")
        self.state_dot = self._label(pill, "●", fg=STATE_COLORS["idle"], bg=CARD)
        self._pack(self.state_dot, side="left", padx=(8, 4), pady=4)
        self.state_label = self._label(pill, "idle", fg=STATE_COLORS["idle"], bg=CARD, font=self.caption_font)
        self._pack(self.state_label, side="left", padx=(0, 8), pady=4)

        # ── Boas-vindas (apenas quando estado == "idle") ──
        snap = read_snapshot(self.state_dir)
        state = display_state(snap["status"], snap["paused"])
        self.welcome_card = None
        if state == "idle":
            self.welcome_card = self._card(outer)
            self._pack(self.welcome_card, fill="x", pady=(4, 0))
            head = self._tk.Frame(self.welcome_card, bg=CARD)
            self._pack(head, fill="x")
            self._pack(
                self._label(head, "👋 Olá! Seu sync do VaultAI está aguardando.",
                    font=self.caption_font, fg=MUTED),
                side="left",
            )
            self._pack(
                self._label(head, "Confira os dados abaixo",
                    font=self.caption_font, fg=MUTED),
                side="right",
            )
            body = self._tk.Frame(self.welcome_card, bg=CARD)
            self._pack(body, fill="x", padx=16)
            self._pack(
                self._label(body, "Sua base do Obsidian está pronta para sincronização.",
                    font=self.font, fg=FG),
                anchor="w",
            )
            self._pack(
                self._label(body, "O pipeline assíncrono processará notas do Apple Notes",
                    font=self.caption_font, fg=MUTED),
                anchor="w",
            )
            self._pack(
                self._label(body, "e organiza automaticamente com MOC e regras de limpeza.",
                font=self.caption_font, fg=MUTED),
                anchor="w",
            )
            self._pack(self._section(body, "Status do sync"), anchor="w", pady=(10, 0))
            self.sync_status = self._label(body, "—", font=self.font, fg=STATE_COLORS["idle"], bg=CARD)
            self._pack(self.sync_status, anchor="w")
            self._pack(self._section(body, "Último sync"), anchor="w", pady=(6, 0))
            self.last_sync_label = self._label(body, "nunca", font=self.caption_font, fg=MUTED, bg=CARD)
            self._pack(self.last_sync_label, anchor="w")
            self._pack(self._section(body, "Totais"), anchor="w", pady=(6, 0))
            self.welcome_totals = self._label(body, "", font=self.caption_font, fg=MUTED, bg=CARD)
            self._pack(self.welcome_totals, anchor="w")

        # ── Métricas ──
        self._pack(self._section(outer, "Métricas"), anchor="w", pady=(10, 0))
        tiles = self._tk.Frame(outer, bg=BG)
        self._pack(tiles, fill="x", pady=(6, 0))
        row1 = self._tk.Frame(tiles, bg=BG)
        self._pack(row1, fill="x", pady=(0, 4))
        row2 = self._tk.Frame(tiles, bg=BG)
        self._pack(row2, fill="x")
        self.metric_labels = {
            "criadas": self._metric(row1, "criadas", "criadas"),
            "atualizadas": self._metric(row1, "atualizadas", "atualizadas"),
            "erros": self._metric(row2, "erros", "erros"),
            "bloqueadas": self._metric(row2, "bloqueadas", "bloqueadas"),
        }
        self.sync_label = self._label(outer, "", fg=MUTED, font=self.caption_font)
        self._pack(self.sync_label, anchor="w", pady=(4, 0))

        # ── Organize ──
        self._pack(self._section(outer, "Organize"), anchor="w", pady=(10, 0))
        self.organize_label = self._label(outer, "")
        self._pack(self.organize_label, anchor="w", pady=(4, 0))

        # ── Status do sync ──
        self._pack(self._section(outer, "Status do sync"), anchor="w", pady=(10, 0))
        self.message_label = self._label(outer, "", fg=MUTED, font=self.caption_font)
        self._pack(self.message_label, anchor="w", pady=(4, 0))

        # ── Progresso ──
        self._pack(self._section(outer, "Progresso"), anchor="w", pady=(10, 0))
        progress = self._card(outer)
        self._pack(progress, fill="x", pady=(4, 0))
        head = self._tk.Frame(progress, bg=CARD)
        self._pack(head, fill="x")
        self._pack(self._section(head, "Progresso"), side="left")
        self.percent_label = self._label(head, "—", font=self.percent_font, fg=ACCENT, bg=CARD, width=120)
        self._pack(self.percent_label, side="right")
        self.bar = self._tk.Canvas(
            progress,
            width=BAR_W,
            height=BAR_H,
            bg=CARD,
            highlightthickness=0,
            borderwidth=0,
        )
        self._pack(self.bar, anchor="w", pady=(8, 0))
        self.progress_label = self._label(progress, "", fg=FG, bg=CARD, font=self.caption_font)
        self._pack(self.progress_label, anchor="w", pady=(6, 2))
        self.activity_label = self._label(progress, "", fg=MUTED, bg=CARD)
        self.activity_label.configure(wraplength=BAR_W)
        self._pack(self.activity_label, anchor="w", pady=(2, 8))

        # ── Progresso ──
        self._pack(self._section(outer, "Progresso"), anchor="w", pady=(10, 0))
        progress = self._card(outer)
        self._pack(progress, fill="x", pady=(4, 0))
        head = self._tk.Frame(progress, bg=CARD)
        self._pack(head, fill="x")
        self._pack(self._section(head, "Progresso"), side="left")
        self.percent_label = self._label(head, "—", font=self.percent_font, fg=ACCENT, bg=CARD, width=120)
        self._pack(self.percent_label, side="right")
        self.bar = self._tk.Canvas(
            progress,
            width=BAR_W,
            height=BAR_H,
            bg=CARD,
            highlightthickness=0,
            borderwidth=0,
        )
        self._pack(self.bar, anchor="w", pady=(8, 0))
        self.progress_label = self._label(progress, "", fg=FG, bg=CARD, font=self.caption_font)
        self._pack(self.progress_label, anchor="w", pady=(6, 2))
        self.activity_label = self._label(progress, "", fg=MUTED, bg=CARD)
        self.activity_label.configure(wraplength=BAR_W)
        self._pack(self.activity_label, anchor="w", pady=(2, 8))

        self.error_label = self._label(outer, "", fg=STATE_COLORS["erro"])
        self.error_label.configure(wraplength=348)
        self._pack(self.error_label, anchor="w", pady=(8, 0))

        # ── Ações (para o estado idle) ──
        self._pack(self._section(outer, "Ações"), anchor="w", pady=(10, 0))
        buttons = self._tk.Frame(outer, bg=BG)
        self._pack(buttons, fill="x", pady=(8, 0))
        self._pack(
            self._button(buttons, "Sincronizar agora", self._on_sync, primary=True),
            fill="x",
        )
        row = self._tk.Frame(buttons, bg=BG)
        self._pack(row, fill="x", pady=(8, 0))
        self._pack(
            self._button(row, "Pausar", self._on_pause),
            side="left",
            expand=True,
            fill="x",
            padx=(0, 4),
        )
        self._pack(
            self._button(row, "Retomar", self._on_resume),
            side="left",
            expand=True,
            fill="x",
            padx=(4, 0),
        )
        links = self._tk.Frame(buttons, bg=BG)
        self._pack(links, fill="x", pady=(8, 0))
        self._pack(
            self._button(links, "Abrir vault", self._on_vault),
            side="left",
            expand=True,
            fill="x",
            padx=(0, 4),
        )
        self._pack(
            self._button(links, "Abrir log", self._on_log),
            side="left",
            expand=True,
            fill="x",
            padx=(4, 0),
        )

        self._paint_bar(None, STATE_COLORS["idle"])
    def _show_idle_state(self):
        """Exibe um estado inicial útil e polido ao abrir a janela."""
        color = STATE_COLORS["idle"]
        self.state_label.configure(text="Pronto", fg=color)
        self.percent_label.configure(text="—", fg=MUTED)
        self.progress_label.configure(text="")
        self.activity_label.configure(text="VaultAI está aguardando o próximo sync automático")
        self.sync_label.configure(text="")
        self.message_label.configure(text="")
        self.error_label.configure(text="")
        for label in self.metric_labels.values():
            label.configure(text="0", fg=MUTED)

    def visible_text(self) -> str:
        parts = []

        def walk(widget):
            try:
                parts.append(str(widget.cget("text")))
            except Exception:
                pass
            for child in widget.winfo_children():
                walk(child)

        walk(self.root)
        return "\n".join(parts)

    def refresh(self):
        snap = read_snapshot(self.state_dir)
        state = display_state(snap["status"], snap["paused"])
        message = snap["status"].get("message") or ""
        color = state_color(state)
        progress = snap["progress"]
        percent = progress_percent(progress)
        metrics = snap["metrics"] or {}
        for key, label in self.metric_labels.items():
            value = metrics.get(key, 0)
            fg = METRIC_COLORS[key] if value else MUTED
            label.configure(text=str(value), fg=fg)
        skipped = "sim" if metrics.get("skipped") else "não"
        self.sync_label.configure(text=f"skipped: {skipped}")
        self.organize_label.configure(text=format_organize_line(snap["organize"]))
        if self._busy and state not in ("sincronizando", "erro") and percent is None:
            self._show_starting()
            return
        self._busy = False
        self.state_label.configure(text=state, fg=color)
        self.state_dot.configure(fg=color)
        self.message_label.configure(text=message)
        self.percent_label.configure(
            text="—" if percent is None else f"{percent}%",
            fg=color if percent is not None else MUTED,
        )
        self.progress_label.configure(text=format_progress_line(progress) or "")
        self.activity_label.configure(text=activity_line(state, message, progress))
        if state == "sincronizando" and percent is None:
            self._kick_indeterminate()
        else:
            self._paint_bar(percent, color)

    def show_error(self, message: str):
        self._busy = False
        self._stop_indeterminate()
        self._error = message
        self.error_label.configure(text=message)
        self.state_label.configure(text="erro", fg=state_color("erro"))
        self.state_dot.configure(fg=state_color("erro"))
        self.activity_label.configure(text=message or "Sync falhou")

    def _on_sync(self):
        self._busy = True
        self._show_starting()
        threading.Thread(target=self._sync_safe, daemon=True).start()

    def _sync_safe(self):
        message = None
        try:
            result = self.actions.pipeline_runner()
        except Exception as exc:
            message = str(exc)
        else:
            if isinstance(result, int) and result != 0:
                message = f"Sync falhou ({result})"

        def finish():
            self._busy = False
            try:
                if not self.root.winfo_exists():
                    return
            except Exception:
                return
            if message:
                self.show_error(message)
                return
            self.refresh()

        try:
            self.root.after(0, finish)
        except Exception:
            self._busy = False

    def _on_pause(self):
        try:
            self.actions.pause()
        except Exception as exc:
            self.show_error(str(exc))
            return
        self.refresh()

    def _on_resume(self):
        try:
            self.actions.resume()
        except Exception as exc:
            self.show_error(str(exc))
            return
        self.refresh()

    def _on_log(self):
        try:
            open_log(self.log_path, opener=self.opener)
        except Exception as exc:
            self.show_error(str(exc))

    def _on_vault(self):
        try:
            open_vault(self.vault_path, opener=self.opener)
        except Exception as exc:
            self.show_error(str(exc))

    def poll(self, interval_ms: int):
        self.refresh()
        self.root.after(interval_ms, lambda: self.poll(interval_ms))


def main():
    from config_import import require

    state_dir, log_file, vault_path, poll = require(
        "STATE_DIR", "PIPELINE_LOG", "VAULT_PATH", "POLL_SECS",
    )
    window = VaultWindow(
        state_dir=state_dir,
        log_path=log_file,
        vault_path=vault_path,
    )

    def _report_mapped(left: int) -> None:
        window.root.update_idletasks()
        if window.root.winfo_viewable():
            print("janela mapeou", flush=True)
            return
        if left <= 0:
            print("janela nao mapeou", flush=True)
            return
        window.root.after(50, _report_mapped, left - 1)

    window.root.after(0, _report_mapped, 40)
    window.poll(max(1, int(poll)) * 1000)
    window.root.mainloop()


if __name__ == "__main__":
    main()
