#!/usr/bin/env python3
"""
organize_vault.py  —  rev3 (Modelo A)
Linking conservador alinhado a práticas PKM/Obsidian:
  1. Título citado no texto (word boundary, >= MIN_TITLE_CHARS)
  2. Tags em comum (Apple Notes)
  - Máx MAX_INLINE_LINKS links inline por nota
  - Sem backlinks automáticos (Obsidian já expõe backlinks nativos)
  - Domínios só em MOCs (_index/), não como critério de link inline
  - Notas lixo excluídas do grafo de links
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from config import (
    VAULT_PATH, DIRTY_FILE, ORGANIZE_LOG as LOG_FILE,
    ORGANIZE_METRICS_FILE,
    LIXO_DIR, MIN_CONTENT_CHARS,
    LIXO_NAME_PATTERNS, DOMAIN_KEYWORDS,
    MAX_INLINE_LINKS, MIN_TITLE_CHARS,
)
from utils import load_json, save_json, extract_note_id

MOC_DIR = "_index"   # pasta dos índices dentro do vault

# ── Regex ─────────────────────────────────────────────────────────────────────

_FM_CAPTURE_RE = re.compile(
    r'^\s*---[ \t]*[\r\n]+(.*?)[\r\n]---[ \t]*[\r\n]*',
    re.DOTALL,
)
_FM_STRIP_RE = re.compile(
    r'^\s*---[ \t]*[\r\n]+.*?[\r\n]---[ \t]*[\r\n]*',
    re.DOTALL,
)
_TAG_ITEM_RE = re.compile(r'^\s+-\s*"?([^"\n]+)"?\s*$')
_LINKS_SECTION_RE = re.compile(
    r'[\r\n]{2}---[\r\n]+## Links relacionados[\r\n]+.*$',
    re.DOTALL,
)

# ── Logging / progresso ───────────────────────────────────────────────────────

def ensure_dirs():
    Path(os.path.expanduser("~/.vault")).mkdir(parents=True, exist_ok=True)

def log(msg: str, verbose_only: bool = False):
    if verbose_only and not ARGS.verbose:
        return
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(f"\r{' ' * 80}\r{line}", flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

_progress_active = False

def progress(i: int, total: int, label: str = ""):
    global _progress_active
    pct    = int(i / total * 100) if total else 0
    filled = int(pct / 4)
    bar    = "█" * filled + "░" * (25 - filled)
    line   = f"  [{bar}] {i:>4}/{total}  {label[:38].ljust(38)}"
    print(f"\r{' ' * 80}\r{line}", end="", flush=True)
    _progress_active = True
    if i >= total:
        print()
        _progress_active = False

def clear_progress():
    global _progress_active
    if _progress_active:
        print(f"\r{' ' * 80}\r", end="", flush=True)
        _progress_active = False

# ── Frontmatter ───────────────────────────────────────────────────────────────

def parse_frontmatter(raw: str) -> dict:
    """
    Extrai campos do frontmatter YAML de forma robusta.
    Suporta strings simples e listas YAML (tags).
    """
    m = _FM_CAPTURE_RE.match(raw)
    if not m:
        return {}
    fm_text = m.group(1)
    result  = {}
    lines   = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"')
            items = []
            j = i + 1
            while j < len(lines):
                item_m = _TAG_ITEM_RE.match(lines[j])
                if item_m:
                    items.append(item_m.group(1).strip().strip('"'))
                    j += 1
                elif lines[j].startswith("  ") or lines[j].startswith("\t"):
                    j += 1
                else:
                    break
            if items:
                result[key] = items
                i = j
            else:
                result[key] = val
                i += 1
        else:
            i += 1
    return result

# ── Lixo ──────────────────────────────────────────────────────────────────────

def read_content(fp: Path) -> str:
    try:
        raw = fp.read_text(encoding="utf-8", errors="ignore")
        return _FM_STRIP_RE.sub("", raw, count=1).strip()
    except Exception:
        return ""

def real_char_count(text: str) -> int:
    t = re.sub(r"\[\[.*?\]\]", "", text)
    t = re.sub(r"#+\s", "", t)
    t = re.sub(r"\s+", "", t)
    return len(t)

def is_lixo_by_name(name: str) -> bool:
    return any(re.match(p, name, re.IGNORECASE) for p in LIXO_NAME_PATTERNS)

def is_lixo_by_content(fp: Path) -> bool:
    if MIN_CONTENT_CHARS == 0:
        return False
    return real_char_count(read_content(fp)) < MIN_CONTENT_CHARS

def move_to_lixo(fp: Path, vault_root: Path, reason: str):
    lixo = vault_root / LIXO_DIR
    lixo.mkdir(parents=True, exist_ok=True)
    dest = lixo / fp.name
    if dest.exists():
        dest = lixo / (fp.stem + f"_{fp.parent.name}" + fp.suffix)
    log(f"  LIXO ({reason})  {fp.relative_to(vault_root)}")
    if not ARGS.dry_run:
        fp.rename(dest)

# ── Domínios (somente MOC) ────────────────────────────────────────────────────

def get_domains(text: str) -> set:
    tl = text.lower()
    return {
        domain
        for domain, kws in DOMAIN_KEYWORDS.items()
        if any(kw in tl for kw in kws)
    }

# ── Indexação ─────────────────────────────────────────────────────────────────

SKIP_DIRS = {LIXO_DIR, MOC_DIR, "_attachments"}

def collect_all_notes(vault_root: Path, dirty_paths: list = None) -> dict:
    """
    Retorna { note_id: { path, stem, domains, tags, ... } }.
    Notas lixo ficam fora do grafo de links.
    """
    dirty_set = set(dirty_paths or [])
    notes     = {}

    for md in vault_root.rglob("*.md"):
        parts = md.relative_to(vault_root).parts
        if any(p in SKIP_DIRS for p in parts):
            continue

        if is_lixo_by_name(md.name):
            continue

        try:
            raw = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        fm       = parse_frontmatter(raw)
        content  = _FM_STRIP_RE.sub("", raw, count=1).strip()
        stem     = md.stem
        note_id  = (
            fm.get("note_id", "").strip().strip('"')
            if isinstance(fm.get("note_id"), str)
            else extract_note_id(raw)
        )
        if not note_id:
            note_id = f"legacy:{md}"

        display_title = (
            fm.get("title", "").strip().strip('"')
            if isinstance(fm.get("title"), str) and fm.get("title")
            else stem
        )

        domains = get_domains(content)

        raw_tags = fm.get("tags", [])
        if isinstance(raw_tags, list):
            tags = {t.lower().strip() for t in raw_tags if t}
        else:
            tags = set()

        tag_domains = tags & DOMAIN_KEYWORDS.keys()
        domains    |= tag_domains

        notes[note_id] = {
            "path":          md,
            "stem":          stem,
            "title":         display_title,
            "link":          stem,
            "note_id":       note_id,
            "domains":       domains,
            "tags":          tags,
            "text":          content.lower(),
            "dirty":         str(md) in dirty_set,
        }

    return notes

# ── Critérios de link (Modelo A) ──────────────────────────────────────────────

def title_mentioned(text: str, title: str) -> bool:
    """Título citado com word boundary — evita matches parciais."""
    if len(title) < MIN_TITLE_CHARS:
        return False
    pattern = r'\b' + re.escape(title.lower()) + r'\b'
    return bool(re.search(pattern, text))

def find_links(note: dict, all_notes: dict) -> list:
    """
    Critérios inline (conservadores):
      1. Título citado no texto (word boundary)
      2. Tags em comum (Apple Notes)
    Prioridade: título > tags. Teto: MAX_INLINE_LINKS.
    """
    candidates: list[tuple[int, str]] = []
    text    = note["text"]
    tags    = note["tags"]
    own_id  = note["note_id"]

    for other_id, other in all_notes.items():
        if other_id == own_id:
            continue

        o_title = other["title"]
        o_link  = other["link"]
        o_tags  = other["tags"]

        if title_mentioned(text, o_title):
            candidates.append((1, o_link))
        elif tags and o_tags and (tags & o_tags):
            candidates.append((2, o_link))

    seen: set[str] = set()
    result: list[str] = []
    for _prio, link in sorted(candidates, key=lambda x: x[0]):
        if link in seen:
            continue
        seen.add(link)
        result.append(link)
        if len(result) >= MAX_INLINE_LINKS:
            break

    return result

# ── Seção de links ────────────────────────────────────────────────────────────

def add_links_section(content: str, links: list) -> str:
    content   = _LINKS_SECTION_RE.sub("", content)
    content   = content.rstrip()
    new_links = sorted(set(l for l in links if f"[[{l}]]" not in content))
    if not new_links:
        return content
    section = "\n\n---\n## Links relacionados\n"
    for l in new_links:
        section += f"- [[{l}]]\n"
    return content + section

def strip_links_sections(vault_root: Path) -> int:
    """Remove seções ## Links relacionados de todo o vault (reset de linking)."""
    cleaned = 0
    for md in vault_root.rglob("*.md"):
        parts = md.relative_to(vault_root).parts
        if any(p in SKIP_DIRS for p in parts):
            continue
        try:
            original = md.read_text(encoding="utf-8", errors="ignore")
            updated  = _LINKS_SECTION_RE.sub("", original).rstrip() + "\n"
            if updated != original:
                if not ARGS.dry_run:
                    md.write_text(updated, encoding="utf-8")
                cleaned += 1
        except Exception:
            pass
    return cleaned

# ── MOC por domínio ───────────────────────────────────────────────────────────

def generate_moc(vault_root: Path, all_notes: dict,
                 only_domains: set[str] | None = None) -> int:
    """
    Gera/atualiza _index/<domínio>.md para cada domínio.
    Domínios não geram links inline — só índices temáticos.
    """
    moc_dir = vault_root / MOC_DIR
    if not ARGS.dry_run:
        moc_dir.mkdir(exist_ok=True)

    domain_map: dict[str, list[str]] = defaultdict(list)
    for n in all_notes.values():
        for d in n["domains"]:
            domain_map[d].append(n["link"])

    generated = 0
    for domain, stems in sorted(domain_map.items()):
        if only_domains is not None and domain not in only_domains:
            continue
        stems_sorted = sorted(set(stems), key=str.lower)
        moc_path     = moc_dir / f"{domain}.md"

        lines = [
            "---\n",
            f'title: "MOC: {domain.title()}"\n',
            "generated: true\n",
            f'domain: "{domain}"\n',
            "---\n\n",
            f"# {domain.title()}\n\n",
            f"*{len(stems_sorted)} nota{'s' if len(stems_sorted) != 1 else ''} "
            f"— gerado automaticamente*\n\n",
        ]
        for stem in stems_sorted:
            lines.append(f"- [[{stem}]]\n")

        new_content = "".join(lines)

        if not ARGS.dry_run:
            existing = moc_path.read_text(encoding="utf-8") if moc_path.exists() else ""
            if new_content != existing:
                moc_path.write_text(new_content, encoding="utf-8")
                generated += 1
        else:
            generated += 1

    return generated

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> bool:
    ensure_dirs()
    label = " [DRY RUN]" if ARGS.dry_run else ""
    log(f"=== organize iniciado{label} ===")

    vault_root = Path(VAULT_PATH)

    dirty_paths: list = []
    if not ARGS.full:
        dirty_data  = load_json(DIRTY_FILE)
        dirty_paths = dirty_data.get("paths", [])
        if not dirty_paths:
            log("Nenhuma nota nova/modificada. Nada a fazer.")
            log("=" * 50)
            return True
        log(f"Processando delta: {len(dirty_paths)} nota(s)")
    else:
        log("Modo --full: processando vault inteiro")

    # ── [ 0 ] Limpar seções de links antigas ──────────────────────────────────
    if ARGS.full:
        log("[ 0 ] Removendo seções ## Links relacionados antigas...")
        n_cleaned = strip_links_sections(vault_root)
        log(f"  → {n_cleaned} arquivo(s) limpo(s)")

    # ── [ 1 ] Lixo ────────────────────────────────────────────────────────────
    log("[ 1 ] Verificando lixo...")
    lixo_count = 0
    targets = (
        [Path(p) for p in dirty_paths]
        if dirty_paths
        else list(vault_root.rglob("*.md"))
    )
    for fp in targets:
        parts = fp.relative_to(vault_root).parts if fp.exists() else ()
        if not fp.exists() or any(p in SKIP_DIRS for p in parts):
            continue
        try:
            fp.relative_to(vault_root)
        except ValueError:
            continue
        if is_lixo_by_name(fp.name):
            move_to_lixo(fp, vault_root, "nome")
            lixo_count += 1
        elif is_lixo_by_content(fp):
            move_to_lixo(fp, vault_root, "conteúdo vazio")
            lixo_count += 1
    log(f"  → {lixo_count} movida(s) para _lixo/")

    # ── [ 2 ] Indexar vault ───────────────────────────────────────────────────
    log("[ 2 ] Indexando vault...")
    all_notes = collect_all_notes(
        vault_root,
        dirty_paths if not ARGS.full else None,
    )
    n_com_dominio = sum(1 for n in all_notes.values() if n["domains"])
    n_com_tags    = sum(1 for n in all_notes.values() if n["tags"])
    log(
        f"  → {len(all_notes)} notas no grafo | "
        f"{n_com_dominio} com domínio (MOC) | "
        f"{n_com_tags} com tags Apple Notes | "
        f"máx {MAX_INLINE_LINKS} links/nota"
    )

    # ── [ 3 ] Links contextuais ───────────────────────────────────────────────
    log("[ 3 ] Criando links contextuais (Modelo A)...")

    process_list = (
        [n for n in all_notes.values() if n["dirty"]]
        if (dirty_paths and not ARGS.full)
        else list(all_notes.values())
    )

    linked        = 0
    n_sem_sinal   = 0
    n_sem_links   = 0
    n_ja_linkada  = 0
    n_limpas      = 0

    total = len(process_list)
    for idx, note in enumerate(process_list, 1):
        progress(idx, total, note["stem"])

        links = find_links(note, all_notes)

        fp = note["path"]
        if not fp.exists():
            continue

        try:
            original = fp.read_text(encoding="utf-8", errors="ignore")
            updated  = add_links_section(original, links)

            if updated == original:
                if links:
                    n_ja_linkada += 1
                elif not links:
                    had_section = bool(_LINKS_SECTION_RE.search(original))
                    if had_section:
                        n_limpas += 1
                    elif note["tags"]:
                        n_sem_links += 1
                    else:
                        n_sem_sinal += 1
                continue

            if not ARGS.dry_run:
                fp.write_text(updated, encoding="utf-8")

            if links:
                linked += 1
            else:
                n_limpas += 1

        except Exception as e:
            clear_progress()
            log(f"  ERRO  {note['path'].name}: {e}")

    clear_progress()

    # ── [ 4 ] MOC por domínio ─────────────────────────────────────────────────
    log("[ 4 ] Gerando MOC por domínio...")
    affected_domains = None
    if dirty_paths and not ARGS.full:
        affected_domains = set()
        for n in all_notes.values():
            if n["dirty"]:
                affected_domains |= n["domains"]
    moc_count = generate_moc(vault_root, all_notes, affected_domains)

    log(
        f"  → {linked} linkadas | {n_limpas} limpas (sem seção) | "
        f"{moc_count} MOC(s)"
    )
    log(
        f"  → ignoradas: {n_sem_sinal} sem sinal | "
        f"{n_sem_links} sem link | "
        f"{n_ja_linkada} já linkadas"
    )

    if not ARGS.dry_run:
        save_json(DIRTY_FILE, {
            "generated_at": datetime.now().isoformat(),
            "paths": [],
        })
        save_json(ORGANIZE_METRICS_FILE, {
            "generated_at":     datetime.now().isoformat(),
            "lixo":             lixo_count,
            "linkadas":         linked,
            "limpas":           n_limpas,
            "mocs":             moc_count,
            "sem_sinal":        n_sem_sinal,
            "sem_links":        n_sem_links,
            "ja_linkadas":      n_ja_linkada,
            "max_inline_links": MAX_INLINE_LINKS,
        })

    log("=" * 50)
    return True


ARGS = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organiza vault Obsidian")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--full",     action="store_true",
                        help="Processa vault inteiro")
    parser.add_argument("--verbose",  action="store_true")
    ARGS = parser.parse_args()
    ok   = main()
    sys.exit(0 if ok else 1)