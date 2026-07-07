#!/usr/bin/env python3
"""Utilitários compartilhados do VaultAI."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

_FILENAME_MAX = 80
_INVALID_CHARS = re.compile(r'[\\/*?:"<>|\n\r\t]')
_NOTE_ID_RE = re.compile(r'^note_id:\s*"?([^"\n]+)"?\s*$', re.MULTILINE)
_HASH_SUFFIX_RE = re.compile(r"_[0-9a-f]{8}$", re.IGNORECASE)
_ALIAS_ITEM_RE = re.compile(r'^\s+-\s*"?([^"\n]+)"?\s*$')


def load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path: str | Path, data: dict) -> None:
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def rotate_log(path: str | Path, max_bytes: int = 5 * 1024 * 1024, backups: int = 3) -> bool:
    p = Path(path)
    if not p.exists() or p.stat().st_size <= max_bytes:
        return False

    oldest = Path(f"{p}.{backups}")
    if oldest.exists():
        oldest.unlink()

    for i in range(backups - 1, 0, -1):
        src = Path(f"{p}.{i}")
        dst = Path(f"{p}.{i + 1}")
        if src.exists():
            src.rename(dst)

    p.rename(Path(f"{p}.1"))
    p.touch()
    return True


def rotate_logs_in_dir(
    directory: str | Path,
    max_bytes: int = 5 * 1024 * 1024,
    backups: int = 3,
) -> int:
    rotated = 0
    for log_file in sorted(Path(directory).glob("*.log")):
        if rotate_log(log_file, max_bytes=max_bytes, backups=backups):
            rotated += 1
    return rotated


def ensure_state_dir(state_dir: str | Path) -> Path:
    path = Path(state_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def note_id_slug(note_id: str) -> str:
    """Reservado para uso interno — NÃO entra no nome do arquivo."""
    return hashlib.md5(note_id.encode()).hexdigest()[:8]


def extract_note_id(raw: str) -> str:
    m = _NOTE_ID_RE.search(raw)
    return m.group(1).strip() if m else ""


def parse_aliases(raw: str) -> list[str]:
    """Extrai lista aliases: do frontmatter YAML."""
    aliases = []
    in_aliases = False
    for line in raw.splitlines():
        if line.strip() == "aliases:":
            in_aliases = True
            continue
        if in_aliases:
            m = _ALIAS_ITEM_RE.match(line)
            if m:
                aliases.append(m.group(1).strip())
            elif line.startswith("  ") or line.startswith("\t"):
                continue
            else:
                break
    return aliases


def merge_aliases(
    existing: list[str],
    old_stem: str | None,
    old_title: str | None,
    new_title: str,
) -> list[str]:
    """Preserva nomes antigos para o Obsidian resolver links legados."""
    out = list(existing)
    for candidate in (old_stem, old_title):
        if not candidate:
            continue
        c = candidate.strip()
        if not c or c == new_title or c in out:
            continue
        out.append(c)
    return out


def format_aliases_yaml(aliases: list[str]) -> str:
    if not aliases:
        return ""
    lines = "aliases:\n" + "\n".join(f'  - "{a}"' for a in aliases)
    return lines + "\n"


def sanitize_title_for_filename(title: str) -> str:
    """
    Política B: nome legível, sem hash.
    - URLs viram host-path
    - Remove reticências e caracteres inválidos
    - Máx 80 caracteres
    """
    t = title.strip()
    t = t.replace("\u2026", "").replace("…", "")
    t = re.sub(r"\s+", " ", t)

    if re.match(r"https?://", t, re.IGNORECASE):
        t = url_to_filename_slug(t)
    else:
        t = _INVALID_CHARS.sub("-", t)
        t = re.sub(r"-+", "-", t)
        t = t.strip(". -")

    if len(t) > _FILENAME_MAX:
        t = t[:_FILENAME_MAX].rstrip(". -")
    return t or "sem-nome"


def url_to_filename_slug(url: str) -> str:
    p = urlparse(url.strip())
    host = p.netloc.replace(":", "-")
    path = p.path.strip("/").replace("/", "-")
    slug = f"{host}-{path}" if path else host
    slug = _INVALID_CHARS.sub("-", slug)
    slug = re.sub(r"-+", "-", slug).strip(". -")
    return slug[:_FILENAME_MAX] or "url"


def _strip_hash_suffix(stem: str) -> str:
    """Remove sufixo legado _a1b2c3d4 de migrações anteriores."""
    return _HASH_SUFFIX_RE.sub("", stem)


def _folder_label(segments: list[str], flat_folders: set[str]) -> str:
    if not segments:
        return ""
    if len(segments) == 1 and segments[0].lower() in flat_folders:
        return segments[0]
    return segments[-1]


def _note_id_at_path(path: Path) -> str:
    try:
        return extract_note_id(path.read_text(encoding="utf-8", errors="ignore")[:1200])
    except Exception:
        return ""


def _is_ours(path: Path) -> bool:
    try:
        return "source: Apple Notes" in path.read_text(encoding="utf-8", errors="ignore")[:500]
    except Exception:
        return False


def unique_filename(
    directory: Path,
    title: str,
    segments: list[str],
    note_id: str,
    flat_folders: set[str],
) -> str:
    """
    Gera nome único e legível dentro do diretório.
    Colisão → 'Título (Pasta).md' → 'Título (Pasta) 2.md' …
    """
    base = sanitize_title_for_filename(title)
    folder = sanitize_title_for_filename(_folder_label(segments, flat_folders))

    candidates = [f"{base}.md"]
    if folder and folder.lower() != base.lower():
        candidates.append(f"{base} ({folder}).md")
    for i in range(2, 25):
        candidates.append(f"{base} ({folder}) {i}.md" if folder else f"{base} {i}.md")

    for cand in candidates:
        fp = directory / cand
        if not fp.exists():
            return cand
        if _is_ours(fp) and _note_id_at_path(fp) == note_id:
            return cand
    return candidates[-1]


def scan_vault_for_note_id(note_id: str, vault_root: Path,
                           skip_dirs: set[str] | None = None) -> Path | None:
    skip = skip_dirs or {"_lixo", "_index", "_attachments"}
    for md in vault_root.rglob("*.md"):
        if any(part in skip for part in md.relative_to(vault_root).parts):
            continue
        try:
            head = md.read_text(encoding="utf-8", errors="ignore")[:1200]
        except Exception:
            continue
        if extract_note_id(head) == note_id:
            return md
    return None


def resolve_human_note_path(
    title: str,
    segments: list[str],
    note_id: str,
    paths_map: dict,
    vault_root: Path,
    target_dir: Path,
    flat_folders: set[str],
    dry_run: bool = False,
) -> tuple[Path, list[str]]:
    """
    Resolve caminho legível para a nota.
    Retorna (path, aliases_acumulados).
    """
    filename = unique_filename(target_dir, title, segments, note_id, flat_folders)
    target   = target_dir / filename
    aliases: list[str] = []

    existing: Path | None = None
    rel = paths_map.get(note_id)
    if rel:
        p = vault_root / rel
        if p.exists():
            existing = p

    if existing is None:
        existing = scan_vault_for_note_id(note_id, vault_root)

    if existing and existing != target:
        try:
            raw = existing.read_text(encoding="utf-8", errors="ignore")
            aliases = merge_aliases(
                parse_aliases(raw),
                existing.stem,
                _strip_hash_suffix(existing.stem),
                title,
            )
        except Exception:
            aliases = merge_aliases([], existing.stem, None, title)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            existing.rename(target)

    elif existing:
        try:
            raw = existing.read_text(encoding="utf-8", errors="ignore")
            aliases = parse_aliases(raw)
        except Exception:
            pass

    if target.exists() and not _is_ours(target) and (existing is None or existing != target):
        raise FileExistsError(target)

    return target, aliases


_IMAGE_EXT_RE = re.compile(r"\.(png|jpg|jpeg|gif|webp|bmp|svg)$", re.IGNORECASE)


def fix_obsidian_embeds(md: str, note_dir: Path | None = None) -> str:
    """
    Corrige wikilinks quebrados após markdownify:
    - Desfaz escape de underscores (\\_ → _)
    - Adiciona prefixo _attachments/ quando o arquivo existe na subpasta
    """
    att_dir = note_dir / "_attachments" if note_dir else None

    def fix_embed(m: re.Match) -> str:
        inner = m.group(1).replace("\\_", "_")
        if att_dir and _IMAGE_EXT_RE.search(inner):
            bare = inner.removeprefix("_attachments/")
            if not inner.startswith("_attachments/") and (att_dir / bare).exists():
                inner = f"_attachments/{bare}"
        return f"![[{inner}]]"

    md = re.sub(r"!\[\[(.*?)\]\]", fix_embed, md)

    def fix_link(m: re.Match) -> str:
        inner = m.group(1).replace("\\_", "_")
        return f"[[{inner}]]"

    return re.sub(r"(?<!!)\[\[(.*?)\]\]", fix_link, md)


def repair_vault_image_embeds(vault_root: Path,
                              skip_dirs: set[str] | None = None) -> int:
    """Repara embeds de imagem em todo o vault. Retorna arquivos alterados."""
    skip = skip_dirs or {"_lixo", "_index"}
    fixed = 0
    for md in vault_root.rglob("*.md"):
        if any(part in skip for part in md.relative_to(vault_root).parts):
            continue
        try:
            original = md.read_text(encoding="utf-8", errors="ignore")
            updated  = fix_obsidian_embeds(original, md.parent)
            if updated != original:
                md.write_text(updated, encoding="utf-8")
                fixed += 1
        except Exception:
            pass
    return fixed


def empty_sync_metrics() -> dict:
    from datetime import datetime
    return {
        "generated_at": datetime.now().isoformat(),
        "criadas": 0,
        "atualizadas": 0,
        "protegidas": 0,
        "erros": 0,
        "skipped": True,
    }