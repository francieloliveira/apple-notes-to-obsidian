#!/usr/bin/env python3
"""
organize_vault.py  —  rev2
Melhorias implementadas:
  A) Tags do Apple Notes (frontmatter) → usadas para links e domínios
  B) Notas da mesma pasta original → links com critério automático
  C) MOC (Map of Content) por domínio em _index/
  D) Breakdown detalhado: sem_sinal / sem_links / já_linkada
  E) Cross-folder: >= 1 domínio em comum (era >= 2)
"""

import argparse
import json
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
    LIXO_DIR, MIN_CONTENT_CHARS,
    LIXO_NAME_PATTERNS, DOMAIN_KEYWORDS,
)

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
            # Verifica se as próximas linhas são itens de lista YAML
            items = []
            j = i + 1
            while j < len(lines):
                item_m = _TAG_ITEM_RE.match(lines[j])
                if item_m:
                    items.append(item_m.group(1).strip().strip('"'))
                    j += 1
                elif lines[j].startswith("  ") or lines[j].startswith("\t"):
                    j += 1   # linha de continuação sem item reconhecido
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

# ── Domínios ──────────────────────────────────────────────────────────────────

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
    Retorna {
        stem_lower: {
            path, stem, domains, tags, apple_folder,
            fs_folder, text, dirty
        }
    }
    A) Tags do Apple Notes (frontmatter) enriquecem os domínios.
    B) apple_folder preserva a pasta original para critério de afinidade.
    """
    dirty_set = set(dirty_paths or [])
    notes     = {}

    for md in vault_root.rglob("*.md"):
        parts = md.relative_to(vault_root).parts
        if any(p in SKIP_DIRS for p in parts):
            continue

        try:
            raw = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        fm      = parse_frontmatter(raw)
        content = _FM_STRIP_RE.sub("", raw, count=1).strip()
        stem    = md.stem

        # Domínios por conteúdo
        domains = get_domains(content)

        # A) Tags do frontmatter (Apple Notes tags)
        raw_tags = fm.get("tags", [])
        if isinstance(raw_tags, list):
            tags = {t.lower().strip() for t in raw_tags if t}
        else:
            tags = set()

        # A) Tags que coincidem com domínios conhecidos enriquecem os domínios
        tag_domains = tags & DOMAIN_KEYWORDS.keys()
        domains    |= tag_domains

        # B) Pasta original do Apple Notes (do frontmatter) e pasta no filesystem
        apple_folder = fm.get("folder", "").strip().strip('"')
        fs_folder    = str(md.parent.relative_to(vault_root))

        notes[stem.lower()] = {
            "path":         md,
            "stem":         stem,
            "domains":      domains,
            "tags":         tags,
            "apple_folder": apple_folder,
            "fs_folder":    fs_folder,
            "text":         content.lower(),
            "dirty":        str(md) in dirty_set,
        }

    return notes

# ── Critérios de link ─────────────────────────────────────────────────────────

def find_links(note: dict, all_notes: dict) -> list:
    """
    Critérios de link (em ordem de prioridade):
      1. Título mencionado no texto (>= 5 chars)
      A) Tags em comum (Apple Notes tags)
      B) Mesma pasta original do Apple Notes (apple_folder)
      E) >= 1 domínio em comum cross-folder (era >= 2)
    """
    links        = []
    text         = note["text"]
    domains      = note["domains"]
    tags         = note["tags"]
    apple_folder = note["apple_folder"]
    own          = note["stem"].lower()

    for sl, other in all_notes.items():
        if sl == own:
            continue

        stem    = other["stem"]
        o_tags  = other["tags"]
        o_af    = other["apple_folder"]
        o_dom   = other["domains"]

        # Critério 1: título da outra nota mencionado no texto desta
        if len(stem) >= 5 and stem.lower() in text:
            links.append(stem)
            continue

        # A) Critério 2: tags em comum do Apple Notes
        if tags and o_tags and (tags & o_tags):
            links.append(stem)
            continue

        # B) Critério 3: mesma pasta original do Apple Notes
        if (apple_folder and o_af
                and apple_folder == o_af
                and apple_folder not in ("", ".")):
            links.append(stem)
            continue

        # E) Critério 4: >= 1 domínio em comum (relaxado de >= 2 para cross-folder)
        if domains and o_dom and (domains & o_dom):
            links.append(stem)

    return links[:25]   # teto de 25 links por nota

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

# ── C) MOC por domínio ────────────────────────────────────────────────────────

def generate_moc(vault_root: Path, all_notes: dict) -> int:
    """
    Gera/atualiza _index/<domínio>.md para cada domínio com a lista
    de notas que pertencem a ele. Só reescreve se o conteúdo mudou.
    """
    moc_dir = vault_root / MOC_DIR
    if not ARGS.dry_run:
        moc_dir.mkdir(exist_ok=True)

    # Agrupa notas por domínio
    domain_map: dict[str, list[str]] = defaultdict(list)
    for n in all_notes.values():
        for d in n["domains"]:
            domain_map[d].append(n["stem"])

    generated = 0
    for domain, stems in sorted(domain_map.items()):
        stems_sorted = sorted(stems, key=str.lower)
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

# ── Utilidades ────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> bool:
    ensure_dirs()
    label = " [DRY RUN]" if ARGS.dry_run else ""
    log(f"=== organize iniciado{label} ===")

    vault_root = Path(VAULT_PATH)

    # Decide quais notas processar
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
        f"  → {len(all_notes)} notas | "
        f"{n_com_dominio} com domínio | "
        f"{n_com_tags} com tags Apple Notes"
    )

    # ── [ 3 ] Links contextuais ───────────────────────────────────────────────
    log("[ 3 ] Criando links contextuais...")

    process_list = (
        [n for n in all_notes.values() if n["dirty"]]
        if (dirty_paths and not ARGS.full)
        else list(all_notes.values())
    )

    backlinks: dict[str, list[str]] = defaultdict(list)

    # D) Contadores detalhados
    linked        = 0
    n_sem_sinal   = 0   # sem domínio E sem tags E sem pasta
    n_sem_links   = 0   # tem sinal mas find_links retornou []
    n_ja_linkada  = 0   # links já existentes, sem mudança

    total = len(process_list)
    for idx, note in enumerate(process_list, 1):
        progress(idx, total, note["stem"])

        links = find_links(note, all_notes)

        if not links:
            has_signal = bool(note["domains"] or note["tags"] or note["apple_folder"])
            if has_signal:
                n_sem_links += 1
            else:
                n_sem_sinal += 1
            continue

        fp = note["path"]
        if not fp.exists():
            continue

        try:
            original = fp.read_text(encoding="utf-8", errors="ignore")
            updated  = add_links_section(original, links)
            if updated == original:
                n_ja_linkada += 1
                continue

            if not ARGS.dry_run:
                fp.write_text(updated, encoding="utf-8")

            for l in links:
                backlinks[l.lower()].append(note["stem"])

            linked += 1

        except Exception as e:
            clear_progress()
            log(f"  ERRO  {note['path'].name}: {e}")

    clear_progress()

    # ── [ 4 ] Backlinks bidirecionais ─────────────────────────────────────────
    log("[ 4 ] Aplicando backlinks bidirecionais...")
    back_applied = 0
    for target_lower, sources in backlinks.items():
        if target_lower not in all_notes:
            continue
        fp = all_notes[target_lower]["path"]
        if not fp.exists():
            continue
        try:
            original = fp.read_text(encoding="utf-8", errors="ignore")
            updated  = add_links_section(original, sources)
            if updated != original and not ARGS.dry_run:
                fp.write_text(updated, encoding="utf-8")
                back_applied += 1
        except Exception:
            pass

    # ── [ 5 ] MOC por domínio ─────────────────────────────────────────────────
    log("[ 5 ] Gerando MOC por domínio...")
    moc_count = generate_moc(vault_root, all_notes)

    # D) Resumo detalhado
    log(
        f"  → {linked} linkadas | {back_applied} backlinks | "
        f"{moc_count} MOC(s)"
    )
    log(
        f"  → ignoradas: {n_sem_sinal} sem sinal | "
        f"{n_sem_links} sem link | "
        f"{n_ja_linkada} já linkadas"
    )
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
