#!/usr/bin/env python3
"""
notes_to_obsidian.py  —  Fase 0 rev3
Export em lotes por pasta: cada pasta é um AppleScript separado,
permitindo acompanhar o progresso em tempo real no terminal.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────────────────
VAULT_PATH   = os.path.expanduser("~/VaultAI")
SYNC_ROOT    = ""
STATE_FILE   = os.path.expanduser("~/.vault/notes_state.json")
IDS_FILE     = os.path.expanduser("~/.vault/notes_ids.json")
DIRTY_FILE       = os.path.expanduser("~/.vault/vault_dirty.json")
CHECKPOINT_FILE  = os.path.expanduser("~/.vault/sync_checkpoint.json")
LOG_FILE         = os.path.expanduser("~/.vault/sync.log")
TIMEZONE     = "America/Sao_Paulo"
FLAT_FOLDERS = {"notes", "notas", "todas (icloud)", "all icloud", "icloud"}
SEP_BODY     = "||VAULTBODY||"   # impossível aparecer em conteúdo de nota
SEP_NOTE     = "||VAULTNOTE||"   # impossível aparecer em conteúdo de nota
# ─────────────────────────────────────────────────────────────────────────────

# ── AppleScripts ──────────────────────────────────────────────────────────────

AS_TREE = r"""
tell application "Notes"
    set output to ""
    repeat with aFolder in every folder
        set fid   to id of aFolder
        set fname to name of aFolder
        set pid   to ""
        try
            set p to container of aFolder
            if class of p is folder then set pid to id of p
        end try
        set output to output & fid & "|||" & fname & "|||" & pid & "\n"
    end repeat
    return output
end tell
"""

# Lista metadados de todas as notas sem o corpo (rápido)
AS_LIST_META = r"""
tell application "Notes"
    set output to ""
    repeat with aFolder in every folder
        set fid to id of aFolder
        repeat with aNote in every note of aFolder
            set nid    to id of aNote
            set ntitle to name of aNote
            set mdate  to modification date of aNote
            set output to output & nid & "|||" & ntitle & "|||" & fid & "|||" & (mdate as string) & "\n"
        end repeat
    end repeat
    return output
end tell
"""

# Exporta o corpo de uma lista de note_ids separados por vírgula
# Retorna blocos separados por <<<NOTE>>>
AS_FETCH_BATCH = r"""
tell application "Notes"
    set noteIds to {IDS_PLACEHOLDER}
    set output to ""
    repeat with nid in noteIds
        try
            set matchNote to first note whose id is nid
            set nbody  to body of matchNote
            set mdate  to modification date of matchNote
            set output to output & nid & "|||" & (mdate as string) & "||VAULTBODY||" & nbody & "||VAULTNOTE||"
        end try
    end repeat
    return output
end tell
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_dirs():
    Path(os.path.expanduser("~/.vault")).mkdir(parents=True, exist_ok=True)

def log(msg: str, verbose_only=False):
    if verbose_only and not ARGS.verbose:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    # Limpa linha do progress bar antes de imprimir log
    print(f"\r{' ' * 80}\r{line}", flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# Linha de progresso atual (salva para saber se precisa limpar)
_progress_active = False

def progress(current: int, total: int, label: str = ""):
    """
    Imprime barra de progresso inline — fica na mesma linha,
    nunca aparece no arquivo de log.
    """
    global _progress_active
    pct    = current / total if total else 0
    filled = int(pct * 25)
    bar    = "█" * filled + "░" * (25 - filled)
    # Trunca o label para caber em 80 cols totais
    label_trunc = label[:35].ljust(35)
    line = f"  [{bar}] {current:>4}/{total} {label_trunc}"
    # Limpa a linha inteira antes de escrever (evita resíduos de texto anterior)
    print(f"\r{' ' * 80}\r{line}", end="", flush=True)
    _progress_active = True
    if current >= total:
        print()   # nova linha ao completar
        _progress_active = False

def clear_progress():
    """Limpa a linha de progresso se estiver ativa."""
    global _progress_active
    if _progress_active:
        print(f"\r{' ' * 80}\r", end="", flush=True)
        _progress_active = False

def run_as(script: str, timeout=120) -> str:
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


# ── Gerenciamento do Notes.app ────────────────────────────────────────────────

AS_NOTES_RUNNING = r"""
tell application "System Events"
    return (name of processes) contains "Notes"
end tell
"""

AS_NOTES_OPEN  = 'tell application "Notes" to activate'
AS_NOTES_QUIT  = 'tell application "Notes" to quit'

_notes_was_running = False   # estado antes do sync — para fechar depois se necessário

def ensure_notes_running():
    """
    Abre o Notes se não estiver rodando.
    Guarda se já estava aberto para não fechar depois.
    """
    global _notes_was_running
    try:
        result = run_as(AS_NOTES_RUNNING, timeout=10)
        _notes_was_running = result.strip().lower() == "true"
    except Exception:
        _notes_was_running = False

    if not _notes_was_running:
        log("     Notes.app não estava rodando — abrindo...")
        run_as(AS_NOTES_OPEN, timeout=15)
        # Aguarda o Notes carregar antes de continuar
        time.sleep(3)
        log("     Notes.app pronto")

def quit_notes_if_we_opened():
    """Fecha o Notes apenas se fomos nós que abrimos."""
    if not _notes_was_running:
        try:
            run_as(AS_NOTES_QUIT, timeout=10)
            log("     Notes.app fechado (estava fechado antes do sync)")
        except Exception:
            pass

def load_json(path: str) -> dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}

def save_json(path: str, data: dict):
    """
    Escrita atômica: grava num .tmp e faz os.replace() — operação POSIX
    atômica. Se o processo morrer no meio, o arquivo original fica intacto.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atômico no macOS/Linux

def sanitize(name: str) -> str:
    safe = re.sub(r'[\\/*?:"<>|]', "-", name)
    safe = safe.strip(". ")
    return safe[:100] or "sem-nome"


# ── Checkpoint ────────────────────────────────────────────────────────────────
# Persiste o progresso a cada CHECKPOINT_EVERY notas gravadas.
# Se o sync for interrompido (crash, sleep, Ctrl+C), a próxima execução
# retoma de onde parou em vez de recomeçar do zero.

CHECKPOINT_EVERY = 50  # salva estado a cada N notas gravadas

def load_checkpoint() -> dict:
    """
    Retorna o checkpoint salvo ou {} se não existir / inválido.
    Formato: { "pending_ids": [...], "state": {...}, "ids": {...},
               "dirty_paths": [...], "created": N, "updated": N }
    """
    data = load_json(CHECKPOINT_FILE)
    # Valida que o checkpoint é da sessão atual (mesmo conjunto de pending)
    if not data or "pending_ids" not in data:
        return {}
    return data

def save_checkpoint(pending_ids: list, state: dict, ids: dict,
                    dirty_paths: list, created: int, updated: int):
    """Salva checkpoint de forma atômica."""
    save_json(CHECKPOINT_FILE, {
        "saved_at":    datetime.now().isoformat(),
        "pending_ids": pending_ids,
        "state":       state,
        "ids":         ids,
        "dirty_paths": dirty_paths,
        "created":     created,
        "updated":     updated,
    })

def clear_checkpoint():
    """Remove o checkpoint após sync bem-sucedido."""
    try:
        Path(CHECKPOINT_FILE).unlink(missing_ok=True)
        # Remove também o .tmp que pode ter sobrado
        Path(CHECKPOINT_FILE + ".tmp").unlink(missing_ok=True)
    except Exception:
        pass

def extract_images(html: str, attachments_dir: Path,
                   note_title: str) -> tuple[str, int]:
    """
    Extrai imagens base64 do HTML, salva como arquivos em attachments_dir
    e substitui os <img> por links Obsidian ![[filename]].

    Retorna (html_sem_base64, quantidade_de_imagens_extraídas).
    """
    attachments_dir.mkdir(parents=True, exist_ok=True)
    count = [0]

    def replace_img(m: re.Match) -> str:
        full_tag = m.group(0)
        src = m.group(1) or m.group(2)  # src com aspas simples ou duplas

        if not src or not src.startswith("data:image/"):
            return full_tag   # não é base64 — mantém a tag

        # Descobre a extensão a partir do media type
        try:
            media, b64 = src.split(",", 1)
            # media = "data:image/png;base64"
            ext = media.split("/")[1].split(";")[0]   # png, jpeg, gif, webp…
            if ext == "jpeg":
                ext = "jpg"
        except Exception:
            return full_tag

        # Nome de arquivo: título_da_nota + índice + hash curto
        count[0] += 1
        short_hash = hashlib.md5(b64[:64].encode()).hexdigest()[:6]
        safe_title = sanitize(note_title)[:40]
        filename   = f"{safe_title}_{count[0]}_{short_hash}.{ext}"
        dest       = attachments_dir / filename

        if not dest.exists():
            try:
                dest.write_bytes(base64.b64decode(b64))
            except Exception:
                return full_tag   # falhou ao decodificar — mantém a tag

        return f"![[{filename}]]"

    # Captura <img ... src="data:..." ...> com aspas duplas ou simples
    pattern = r'<img[^>]+src="(data:image/[^"]+)"[^>]*>|<img[^>]+src=\'(data:image/[^\']+)\'[^>]*>'
    html_out = re.sub(pattern, replace_img, html, flags=re.IGNORECASE | re.DOTALL)
    return html_out, count[0]


def html_to_markdown(html: str, attachments_dir: Path = None,
                     note_title: str = "") -> str:
    """
    Converte HTML do Apple Notes para Markdown.
    Se attachments_dir for fornecido, extrai imagens base64 como arquivos
    e insere links ![[filename]] no lugar.
    """
    t = html

    # Extrai imagens antes de processar o HTML
    if attachments_dir is not None:
        t, n_imgs = extract_images(t, attachments_dir, note_title)

    t = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1',   t, flags=re.DOTALL|re.I)
    t = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1',  t, flags=re.DOTALL|re.I)
    t = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<b[^>]*>(.*?)</b>',           r'**\1**', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<i[^>]*>(.*?)</i>',   r'*\1*', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<li[^>]*class="[^"]*checked[^"]*"[^>]*>(.*?)</li>',
               r'- [x] \1', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', t, flags=re.DOTALL|re.I)
    t = re.sub(r'<[ou]l[^>]*>|</[ou]l>', '', t, flags=re.I)
    t = re.sub(r'</p>|</div>|<br\s*/?>', '\n', t, flags=re.I)
    t = re.sub(r'<p[^>]*>|<div[^>]*>', '\n', t, flags=re.I)
    t = re.sub(r'<[^>]+>', '', t)   # remove tags restantes (img sem base64, etc.)
    for e, r in [('&amp;','&'),('&lt;','<'),('&gt;','>'),
                 ('&nbsp;',' '),('&quot;','"'),('&#39;',"'")]:
        t = t.replace(e, r)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()

# ── Árvore de pastas ──────────────────────────────────────────────────────────

def build_folder_tree() -> dict:
    raw = run_as(AS_TREE, timeout=60)
    folders = {}
    for line in raw.splitlines():
        parts = line.split("|||")
        if len(parts) == 3:
            fid, fname, pid = [p.strip() for p in parts]
            folders[fid] = (fname, pid)

    cache = {}
    def resolve(fid, visited=None):
        visited = visited or set()
        if fid in cache: return cache[fid]
        if fid in visited or fid not in folders: return []
        visited = visited | {fid}
        fname, pid = folders[fid]
        path = (resolve(pid, visited) + [fname]) if (pid and pid in folders) else [fname]
        cache[fid] = path
        return path

    return {fid: resolve(fid) for fid in folders}

# ── Lista de metadados (sem corpo) ────────────────────────────────────────────

def list_meta() -> list:
    """Retorna [(note_id, title, folder_id, mod_date)] — rápido, sem corpo."""
    raw = run_as(AS_LIST_META, timeout=120)
    notes, seen = [], set()
    for line in raw.splitlines():
        parts = line.split("|||")
        if len(parts) == 4:
            nid, title, fid, mdate = [p.strip() for p in parts]
            key = (nid, fid)
            if key not in seen:
                seen.add(key)
                notes.append((nid, title, fid, mdate))
    return notes

# ── Fetch paralelo (um osascript por nota, N workers simultâneos) ─────────────

AS_FETCH_ONE = r"""
tell application "Notes"
    set matchNote to first note whose id is "{note_id}"
    set mdate to modification date of matchNote
    return (mdate as string) & "||VAULTDATE||" & body of matchNote
end tell
"""

FETCH_WORKERS = 8

def fetch_one(note_id: str, timeout: int = 30) -> tuple:
    """
    Busca corpo + data de modificação de uma nota por ID.
    Retorna (note_id, body_html, mod_date) ou (note_id, "", "") em caso de erro.
    """
    script = AS_FETCH_ONE.replace("{note_id}", note_id)
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        if r.returncode == 0:
            out = r.stdout
            if "||VAULTDATE||" in out:
                mod_date, body = out.split("||VAULTDATE||", 1)
                return note_id, body, mod_date.strip()
            return note_id, out, ""
        return note_id, "", ""
    except Exception:
        return note_id, "", ""


def fetch_needed(pending: list, folder_tree: dict) -> dict:
    """
    Busca corpos em paralelo.
    Retorna { note_id: (body_html, mod_date_from_fetch) }
    A mod_date vem do mesmo AppleScript que o corpo — mesma fonte, sem divergência.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total  = len(pending)
    bodies = {}
    failed = 0

    log(f"     Buscando conteúdo ({total} notas, {FETCH_WORKERS} workers paralelos)...")

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        futures = {
            executor.submit(fetch_one, n[0]): n
            for n in pending
        }
        done = 0
        for future in as_completed(futures):
            note    = futures[future]
            note_id = note[0]
            title   = note[1]
            fid     = note[2]
            segs    = folder_tree.get(fid, ["?"])
            label   = "/".join(segs[-2:])

            try:
                nid, body, mod_date = future.result()
                if body:
                    bodies[nid] = (body, mod_date)
                else:
                    failed += 1
            except Exception:
                failed += 1

            done += 1
            progress(done, total, f"{title[:30]}  [{label}]")

    clear_progress()
    if failed:
        log(f"  !! {failed} nota(s) sem conteúdo")
    log(f"     Conteúdo obtido: {len(bodies)}/{total}")

    return bodies

# ── Vault ─────────────────────────────────────────────────────────────────────

def vault_dir(segments: list) -> Path:
    base = Path(VAULT_PATH)
    if SYNC_ROOT:
        base = base / SYNC_ROOT
    if not (len(segments) == 1 and segments[0].lower() in FLAT_FOLDERS):
        for s in segments:
            base = base / sanitize(s)
    base.mkdir(parents=True, exist_ok=True)
    return base

def note_is_ours(fp: Path) -> bool:
    try:
        return "source: Apple Notes" in fp.read_text(encoding="utf-8")[:500]
    except Exception:
        return False

def write_note(title: str, segments: list, body_html: str,
               mod_date: str, note_id: str) -> Path:
    """
    Converte HTML → Markdown (extraindo imagens), escreve o .md no vault.
    Imagens são salvas em _attachments/ dentro da mesma pasta da nota.
    """
    d  = vault_dir(segments)
    fp = d / (sanitize(title) + ".md")

    if fp.exists() and not note_is_ours(fp):
        raise FileExistsError(fp)

    if ARGS.dry_run:
        return fp

    # Pasta de anexos: mesma pasta da nota / _attachments
    attachments_dir = d / "_attachments"

    folder_path = "/".join(segments)
    content     = html_to_markdown(body_html,
                                   attachments_dir=attachments_dir,
                                   note_title=title)

    fm = (f'---\n'
          f'title: "{title}"\n'
          f'folder: "{folder_path}"\n'
          f'source: Apple Notes\n'
          f'note_id: "{note_id}"\n'
          f'synced_at: "{datetime.now(ZoneInfo(TIMEZONE)).isoformat()}"\n'
          f'apple_notes_modified: "{mod_date}"\n'
          f'---\n\n')
    fp.write_text(fm + content, encoding="utf-8")
    return fp

# ── Sync principal ────────────────────────────────────────────────────────────

def sync():
    ensure_dirs()
    label = " [DRY RUN]" if ARGS.dry_run else ""
    log(f"=== sync iniciado{label} ===")

    # Garante que o Notes está rodando antes de qualquer AppleScript
    ensure_notes_running()

    log("1/4  Mapeando árvore de pastas...")
    tree = build_folder_tree()
    log(f"     Pastas: {len(tree)}")

    state = {} if ARGS.full else load_json(STATE_FILE)
    ids   = {} if ARGS.full else load_json(IDS_FILE)

    log("2/4  Listando metadados...")
    all_meta = list_meta()
    log(f"     Notas encontradas: {len(all_meta)}")

    # Filtra só as que precisam de sync
    # Chave: note_id (estável, único, imune a renomeação de pasta/título)
    pending = []
    for (nid, title, fid, mdate) in all_meta:
        state_key = nid   # usa o note_id diretamente como chave
        if state.get(state_key) != mdate or ARGS.full:
            pending.append((nid, title, fid, mdate))

    log(f"3/4  Notas a processar: {len(pending)} "
        f"(ignoradas: {len(all_meta) - len(pending)})")

    if not pending:
        log("     Tudo atualizado. Nada a fazer.")
        save_json(DIRTY_FILE, {"generated_at": datetime.now().isoformat(), "paths": []})
        clear_checkpoint()
        log("=== sync concluido ===")
        return True

    # ── Verifica checkpoint de sessão anterior ─────────────────────────────
    ckpt = {} if ARGS.full else load_checkpoint()
    pending_ids_now = [n[0] for n in pending]

    if ckpt and set(ckpt.get("pending_ids", [])) == set(pending_ids_now):
        already_done = set(ckpt["pending_ids"]) - set(
            n[0] for n in pending if ckpt["state"].get(f"{n[2]}/{n[1]}") != n[3]
        )
        remaining = [n for n in pending if n[0] not in set(ckpt.get("state", {}).values())]

        # Retoma estado do checkpoint
        state       = ckpt["state"]
        ids         = ckpt["ids"]
        dirty_paths = ckpt["dirty_paths"]
        created     = ckpt["created"]
        updated     = ckpt["updated"]

        # Filtra pending para só o que ainda não foi gravado
        done_keys = set(state.keys())
        pending   = [n for n in pending
                     if f"{n[2]}/{n[1]}" not in done_keys]

        resumed = len(pending_ids_now) - len(pending)
        if resumed:
            log(f"     Retomando checkpoint: {resumed} notas já gravadas, "
                f"{len(pending)} restantes")
    else:
        if ckpt:
            log("     Checkpoint inválido (notas mudaram) — iniciando do zero")
            clear_checkpoint()
        dirty_paths = []
        created = updated = 0

    if not pending:
        log("     Todas as notas já gravadas (via checkpoint).")
        save_json(DIRTY_FILE, {
            "generated_at": datetime.now().isoformat(),
            "paths": dirty_paths
        })
        clear_checkpoint()
        log("=== sync concluido ===")
        return True

    # Etapa 3: busca corpos em lotes com retry
    if ARGS.dry_run:
        bodies = {}
    else:
        bodies = fetch_needed(pending, tree)
        clear_progress()
        log(f"     Conteúdo obtido: {len(bodies)}/{len(pending)} notas")

    log(f"4/4  Gravando no vault...")
    protected = errors = 0
    total_w   = len(pending)

    for i, (note_id, title, folder_id, mod_date) in enumerate(pending, 1):
        state_key = note_id   # chave estável = note_id
        try:
            segments = tree.get(folder_id)
            if not segments:
                clear_progress()
                log(f"  !! folder não encontrado: {folder_id} / '{title}'")
                errors += 1
                progress(i, total_w, f"erro  {title[:35]}")
                continue

            is_new            = state.get(state_key) is None
            fetched           = bodies.get(note_id, ("", ""))
            body_html         = fetched[0]
            # Usa a data do fetch_one — mesma fonte que será consultada
            # no próximo ciclo, eliminando divergências de fuso/formato
            mod_date_to_save  = fetched[1] if fetched[1] else mod_date
            fp                = write_note(title, segments, body_html,
                                           mod_date_to_save, note_id)

            if not ARGS.dry_run:
                state[state_key] = mod_date_to_save  # data consistente
                ids[state_key]   = note_id
                dirty_paths.append(str(fp))

            if is_new:
                created += 1
            else:
                updated += 1

            # ── Checkpoint periódico ───────────────────────────────────────
            if not ARGS.dry_run and i % CHECKPOINT_EVERY == 0:
                remaining_ids = [n[0] for n in pending[i:]]
                save_checkpoint(remaining_ids, state, ids,
                                dirty_paths, created, updated)
                log(f"  .. checkpoint: {i}/{total_w} notas gravadas",
                    verbose_only=True)

            action = "criada" if is_new else "atualiz"
            progress(i, total_w, f"{action}  {title[:35]}")

        except FileExistsError as e:
            clear_progress()
            protected += 1
            log(f"  --  PROTEGIDA '{title}'")
        except Exception as e:
            clear_progress()
            errors += 1
            log(f"  !!  ERRO '{title}': {e}")

    clear_progress()

    if not ARGS.dry_run:
        save_json(STATE_FILE, state)
        save_json(IDS_FILE, ids)
        save_json(DIRTY_FILE, {
            "generated_at": datetime.now().isoformat(),
            "paths": dirty_paths
        })
        # Remove checkpoint só se tudo correu bem
        if errors == 0:
            clear_checkpoint()
        else:
            log(f"  .. checkpoint mantido ({errors} erros) — próximo sync retoma")

    log(f"     criadas:{created}  atualizadas:{updated}  "
        f"protegidas:{protected}  erros:{errors}")
    log("=== sync concluido ===")
    log("=" * 50)

    # Fecha o Notes se foi o script que abriu
    quit_notes_if_we_opened()

    return errors == 0

# ── Entry point ───────────────────────────────────────────────────────────────

ARGS = None

def main():
    global ARGS
    parser = argparse.ArgumentParser(description="Sync Apple Notes → Obsidian")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--full",     action="store_true")
    parser.add_argument("--verbose",  action="store_true")
    ARGS = parser.parse_args()
    ok = sync()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
