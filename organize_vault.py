#!/usr/bin/env python3
"""
organize_vault.py  —  Fase 0
- Lê .vault_dirty.json para processar só notas novas/modificadas
- Detecta lixo por nome E por conteúdo (< 20 chars reais)
- Cria links contextuais bidirecionais
- Links por domínio com validação de contexto mínimo
- CLI: --dry-run, --full, --verbose
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


def ensure_dirs():
    Path(os.path.expanduser("~/.vault")).mkdir(parents=True, exist_ok=True)

def log(msg: str, verbose_only=False):
    if verbose_only and not ARGS.verbose:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_json(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}

_FRONTMATTER_RE = re.compile(
    r'^\s*---[ \t]*[\r\n]+'   # --- de abertura (com possível \r\n)
    r'.*?'                     # corpo do frontmatter (lazy, qualquer coisa)
    r'[\r\n]---[ \t]*[\r\n]*', # --- de fechamento
    re.DOTALL,
)

def read_content(fp: Path) -> str:
    try:
        raw = fp.read_text(encoding="utf-8", errors="ignore")
        raw = _FRONTMATTER_RE.sub('', raw, count=1)
        return raw.strip()
    except Exception:
        return ""

def real_char_count(text: str) -> int:
    """Conta chars depois de remover markdown, links, espaços."""
    t = re.sub(r'\[\[.*?\]\]', '', text)
    t = re.sub(r'#+\s', '', t)
    t = re.sub(r'\s+', '', t)
    return len(t)

def is_lixo_by_name(name: str) -> bool:
    for p in LIXO_NAME_PATTERNS:
        if re.match(p, name, re.IGNORECASE):
            return True
    return False

def is_lixo_by_content(fp: Path) -> bool:
    """Desativado por padrão (MIN_CONTENT_CHARS=0). Notas vazias são válidas —
    o usuário decide o que descartar manualmente."""
    if MIN_CONTENT_CHARS == 0:
        return False
    content = read_content(fp)
    return real_char_count(content) < MIN_CONTENT_CHARS

def get_domains(text: str) -> set:
    tl = text.lower()
    found = set()
    for domain, kws in DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw in tl:
                found.add(domain)
                break
    return found

def add_links_section(content: str, links: list) -> str:
    # Remove seção anterior gerada automaticamente (tolerante a \r\n)
    content = re.sub(
        r'[\r\n]{2}---[\r\n]+## Links relacionados[\r\n]+.*$',
        '', content, flags=re.DOTALL,
    )
    content = content.rstrip()
    new_links = sorted(set(l for l in links if f"[[{l}]]" not in content))
    if not new_links:
        return content
    section = "\n\n---\n## Links relacionados\n"
    for l in new_links:
        section += f"- [[{l}]]\n"
    return content + section

def collect_all_notes(vault_root: Path, only_paths: list = None) -> dict:
    """
    Retorna { stem_lower: {path, stem, domains, folder, text} }
    Se only_paths fornecido, indexa o vault todo mas marca quais são "dirty"
    para processar links só nelas (evita re-processar notas intocadas).
    """
    dirty_set = set(only_paths or [])
    notes = {}
    for md in vault_root.rglob("*.md"):
        if LIXO_DIR in str(md):
            continue
        stem = md.stem
        text = read_content(md)
        notes[stem.lower()] = {
            "path":    md,
            "stem":    stem,
            "domains": get_domains(text),
            "folder":  str(md.parent.relative_to(vault_root)),
            "text":    text.lower(),
            "dirty":   str(md) in dirty_set,
        }
    return notes

def find_links(note: dict, all_notes: dict) -> list:
    links = []
    text    = note["text"]
    domains = note["domains"]
    folder  = note["folder"]
    own     = note["stem"].lower()

    for sl, other in all_notes.items():
        if sl == own or not other["domains"]:
            continue
        stem = other["stem"]
        # Critério 1: título mencionado no texto (mín 6 chars para evitar falso positivo)
        if len(stem) >= 6 and stem.lower() in text:
            links.append(stem)
            continue
        # Critério 2: domínios em comum com limiar por distância
        common = domains & other["domains"]
        if not common:
            continue
        same_folder = folder == other["folder"]
        if (same_folder and len(common) >= 1) or (not same_folder and len(common) >= 2):
            links.append(stem)

    return links[:20]

def move_to_lixo(fp: Path, vault_root: Path, reason: str):
    lixo = vault_root / LIXO_DIR
    lixo.mkdir(parents=True, exist_ok=True)
    dest = lixo / fp.name
    if dest.exists():
        dest = lixo / (fp.stem + f"_{fp.parent.name}" + fp.suffix)
    rel = fp.relative_to(vault_root)
    log(f"  LIXO ({reason})  {rel}")
    if not ARGS.dry_run:
        fp.rename(dest)

def main():
    ensure_dirs()
    log("=== organize iniciado" + (" [DRY RUN]" if ARGS.dry_run else "") + " ===")

    vault_root = Path(VAULT_PATH)

    # Decide quais notas processar
    dirty_paths = []
    if not ARGS.full:
        dirty_data  = load_json(DIRTY_FILE)
        dirty_paths = dirty_data.get("paths", [])
        if not dirty_paths:
            log("Nenhuma nota nova/modificada (.vault_dirty.json vazio). Nada a fazer.")
            log("=" * 50)
            return True
        log(f"Processando delta: {len(dirty_paths)} nota(s) tocada(s)")
    else:
        log("Modo --full: processando vault inteiro")

    # ── Passo 1: lixo ──────────────────────────────────────────────
    log("[ 1 ] Verificando lixo...")
    lixo_count = 0
    targets = [Path(p) for p in dirty_paths] if dirty_paths else list(vault_root.rglob("*.md"))
    for fp in targets:
        if not fp.exists() or LIXO_DIR in str(fp):
            continue
        try:
            fp.relative_to(vault_root)
        except ValueError:
            continue  # arquivo fora do vault_root (ex: caminho antigo) — ignora
        if is_lixo_by_name(fp.name):
            move_to_lixo(fp, vault_root, "nome")
            lixo_count += 1
        elif is_lixo_by_content(fp):
            move_to_lixo(fp, vault_root, "conteúdo vazio")
            lixo_count += 1
    log(f"  → {lixo_count} movida(s) para _lixo/")

    # ── Passo 2: indexar vault ──────────────────────────────────────
    log("[ 2 ] Indexando vault...", verbose_only=True)
    all_notes = collect_all_notes(vault_root, dirty_paths if not ARGS.full else None)
    log(f"  → {len(all_notes)} notas indexadas", verbose_only=True)

    # ── Passo 3: links contextuais (só notas dirty ou full) ────────
    log("[ 3 ] Criando links contextuais...")
    linked = skipped = 0

    process_list = (
        [n for n in all_notes.values() if n["dirty"]]
        if (dirty_paths and not ARGS.full)
        else list(all_notes.values())
    )

    # Índice reverso: quais notas vão receber backlink
    backlinks: dict[str, list[str]] = defaultdict(list)

    for note in process_list:
        if not note["domains"]:
            skipped += 1
            continue

        links = find_links(note, all_notes)
        if not links:
            skipped += 1
            continue

        fp = note["path"]
        if not fp.exists():
            continue

        try:
            original = fp.read_text(encoding="utf-8", errors="ignore")
            updated  = add_links_section(original, links)
            if updated == original:
                skipped += 1
                continue

            log(f"  LINK  {fp.relative_to(vault_root)}")
            for l in sorted(set(links))[:4]:
                log(f"        → [[{l}]]", verbose_only=True)

            if not ARGS.dry_run:
                fp.write_text(updated, encoding="utf-8")

            # Registra backlinks para aplicar no passo seguinte
            for l in links:
                backlinks[l.lower()].append(note["stem"])

            linked += 1
        except Exception as e:
            log(f"  ERRO  {fp.name}: {e}")

    # ── Passo 4: backlinks bidirecionais ───────────────────────────
    log("[ 4 ] Aplicando backlinks bidirecionais...")
    back_applied = 0
    for target_lower, sources in backlinks.items():
        if target_lower not in all_notes:
            continue
        target_note = all_notes[target_lower]
        fp = target_note["path"]
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

    log(f"  → {linked} notas com links | {back_applied} backlinks | {skipped} ignoradas")
    log("=" * 50)
    return True


ARGS = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organiza vault Obsidian")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--full",     action="store_true", help="Processa vault inteiro")
    parser.add_argument("--verbose",  action="store_true")
    ARGS = parser.parse_args()
    ok = main()
    sys.exit(0 if ok else 1)
