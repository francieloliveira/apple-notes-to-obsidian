#!/usr/bin/env python3
"""
pipeline.py  —  Fase 1 (orquestrador)
Executa: sync → organize
- Lock file evita execuções simultâneas
- Timeout global por etapa
- Log unificado
- Notificação macOS em caso de falha
- CLI: --dry-run, --full, --verbose
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────────────────
SCRIPTS_DIR  = os.getenv("SCRIPTS_DIR", "/usr/local/bin")
LOCK_FILE    = "/tmp/vault_pipeline.lock"
LOG_FILE     = os.path.expanduser("~/.vault/pipeline.log")
STATUS_FILE  = os.path.expanduser("~/.vault/status.json")  # lido pelo menu bar
STEP_TIMEOUT = 700  # segundos por etapa
# ─────────────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def save_status(state: str, message: str = "", metrics: dict = None):
    """
    Grava status.json para o menu bar ler.
    state: "running" | "ok" | "error" | "idle"
    """
    data = {
        "state":      state,
        "message":    message,
        "updated_at": datetime.now().isoformat(),
        "metrics":    metrics or {},
    }
    tmp = STATUS_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, STATUS_FILE)
    except Exception:
        pass

def notify_rich(title: str, subtitle: str, message: str,
                sound: str = "Glass"):
    """Notificação macOS rica com título, subtítulo e corpo."""
    script = (
        f'display notification "{message}" '
        f'with title "{title}" '
        f'subtitle "{subtitle}" '
        f'sound name "{sound}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], timeout=5)
    except Exception:
        pass

def notify(title: str, message: str):
    """Compat: notificação simples (usada em erros)."""
    notify_rich(title, "", message, sound="Basso")

def acquire_lock() -> bool:
    lock = Path(LOCK_FILE)
    if lock.exists():
        try:
            age = time.time() - lock.stat().st_mtime
            if age < STEP_TIMEOUT * 2:
                log(f"!! Lock ativo ({age:.0f}s). Pipeline já em execução. Saindo.")
                return False
            else:
                log(f"Lock antigo ({age:.0f}s). Removendo e continuando.")
                lock.unlink()
        except Exception:
            pass
    lock.write_text(str(os.getpid()))
    return True

def release_lock():
    try:
        Path(LOCK_FILE).unlink(missing_ok=True)
    except Exception:
        pass

def run_step(name: str, script: str, extra_args: list = None) -> bool:
    cmd = [sys.executable, script] + (extra_args or [])
    log(f"-- {name} iniciado")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, timeout=STEP_TIMEOUT,
                           capture_output=False, text=True)
        elapsed = time.time() - t0
        if r.returncode == 0:
            log(f"-- {name} OK ({elapsed:.1f}s)")
            return True
        else:
            log(f"!! {name} FALHOU com código {r.returncode} ({elapsed:.1f}s)")
            return False
    except subprocess.TimeoutExpired:
        log(f"!! {name} TIMEOUT após {STEP_TIMEOUT}s")
        return False
    except Exception as e:
        log(f"!! {name} ERRO: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Pipeline vault Obsidian")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--full",     action="store_true")
    parser.add_argument("--verbose",  action="store_true")
    args = parser.parse_args()

    extra = []
    if args.dry_run: extra.append("--dry-run")
    if args.full:    extra.append("--full")
    if args.verbose: extra.append("--verbose")

    Path(os.path.expanduser("~/.vault")).mkdir(parents=True, exist_ok=True)

    log("=" * 55)
    log("=== PIPELINE INICIADO" + (" [DRY RUN]" if args.dry_run else "") + " ===")

    if not acquire_lock():
        sys.exit(1)

    t_start = time.time()
    save_status("running", "Sincronizando Apple Notes...")

    try:
        sync_ok = run_step(
            "sync",
            f"{SCRIPTS_DIR}/notes_to_obsidian.py",
            extra
        )

        if not sync_ok:
            save_status("error", "Sync falhou")
            notify_rich(
                "VaultAI",
                "Sync falhou",
                "Erro ao sincronizar Apple Notes. Ver ~/.vault/pipeline.log",
                sound="Basso"
            )
            sys.exit(1)

        save_status("running", "Organizando vault...")

        org_ok = run_step(
            "organize",
            f"{SCRIPTS_DIR}/organize_vault.py",
            extra
        )

        elapsed = time.time() - t_start

        # Lê métricas gravadas pelo sync
        metrics = _read_sync_metrics()
        criadas   = metrics.get("criadas", 0)
        atualizadas = metrics.get("atualizadas", 0)
        erros     = metrics.get("erros", 0)

        if not org_ok:
            save_status("error", "Organização falhou", metrics)
            notify_rich(
                "VaultAI",
                "Organização falhou",
                f"Sync ok ({criadas} novas, {atualizadas} atualizadas) "
                f"mas organização teve erro.",
                sound="Basso"
            )
            sys.exit(1)

        # ── Tudo ok: notificação rica + status ─────────────────────────────
        parts = []
        if criadas:     parts.append(f"{criadas} nova{'s' if criadas != 1 else ''}")
        if atualizadas: parts.append(f"{atualizadas} atualizada{'s' if atualizadas != 1 else ''}")
        if erros:       parts.append(f"{erros} erro{'s' if erros != 1 else ''}")

        summary  = "  ·  ".join(parts) if parts else "Tudo atualizado"
        subtitle = f"concluído em {elapsed:.0f}s"

        save_status("ok", summary, {**metrics, "elapsed_s": round(elapsed, 1)})

        if not args.dry_run:
            notify_rich(
                "VaultAI",
                subtitle,
                summary,
                sound="Glass"
            )

        log("=== PIPELINE CONCLUÍDO ===")
        log("=" * 55)

    except KeyboardInterrupt:
        save_status("error", "Interrompido")
        log("!! Pipeline interrompido pelo usuário")
    finally:
        release_lock()


def _read_sync_metrics() -> dict:
    """Lê a última linha de métricas do sync log."""
    try:
        log_path = Path(os.path.expanduser("~/.vault/sync.log"))
        if not log_path.exists():
            return {}
        lines = log_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if "criadas:" in line and "atualizadas:" in line:
                m = {}
                for part in line.split("  "):
                    if ":" in part:
                        k, v = part.strip().split(":", 1)
                        try:
                            m[k.strip()] = int(v.strip())
                        except ValueError:
                            pass
                return m
    except Exception:
        pass
    return {}

if __name__ == "__main__":
    main()
