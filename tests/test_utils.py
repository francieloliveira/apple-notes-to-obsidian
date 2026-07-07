#!/usr/bin/env python3
"""Testes unitários do VaultAI."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notes_to_obsidian import normalize_date
from utils import (
    extract_note_id, empty_sync_metrics, merge_aliases,
    sanitize_title_for_filename, unique_filename, url_to_filename_slug,
    fix_obsidian_embeds,
)


class TestTitlePolicy(unittest.TestCase):
    def test_no_hash_in_filename(self):
        name = sanitize_title_for_filename("Reunião Petrobras")
        self.assertNotRegex(name, r"_[0-9a-f]{8}$")
        self.assertEqual(name, "Reunião Petrobras")

    def test_url_becomes_readable_slug(self):
        url = "https://premium-dsv-outsystems.petrobras.com.br/S10865_Autonomia"
        slug = url_to_filename_slug(url)
        self.assertTrue(slug.startswith("premium-dsv-outsystems"))
        self.assertNotIn("://", slug)

    def test_strips_ellipsis(self):
        t = "Para atualizar o Open WebUI no Docker…"
        self.assertNotIn("…", sanitize_title_for_filename(t))

    def test_collision_uses_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            other = d / "daily.md"
            other.write_text('---\nnote_id: "other-id"\nsource: Apple Notes\n---\n')
            name = unique_filename(
                d, "daily", ["Canal Motorista"], "my-note-id", set(),
            )
            self.assertNotEqual(name, "daily.md")

    def test_same_note_id_reuses_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            nid = "x-coredata://ABC/ICNote/p1"
            existing = d / "daily.md"
            existing.write_text(f'---\nnote_id: "{nid}"\nsource: Apple Notes\n---\n')
            name = unique_filename(d, "daily", ["PDA"], nid, set())
            self.assertEqual(name, "daily.md")


class TestAliases(unittest.TestCase):
    def test_merge_skips_duplicate_and_new_title(self):
        result = merge_aliases(
            ["Old Name"],
            "Old Name_a1b2c3d4",
            "Old Name",
            "New Name",
        )
        self.assertIn("Old Name", result)
        self.assertIn("Old Name_a1b2c3d4", result)
        self.assertNotIn("New Name", result)


class TestNormalizeDate(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(
            normalize_date("  Segunda,  1  de  janeiro  "),
            normalize_date("segunda, 1 de janeiro"),
        )


class TestExtractNoteId(unittest.TestCase):
    def test_from_frontmatter(self):
        raw = '---\nnote_id: "abc-123"\ntitle: "x"\n---\n\nbody'
        self.assertEqual(extract_note_id(raw), "abc-123")


class TestImageEmbeds(unittest.TestCase):
    def test_unescapes_underscores_and_adds_attachments_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            att = d / "_attachments"
            att.mkdir()
            (att / "note_1_abc123.png").write_bytes(b"png")
            md = "![[note\\_1\\_abc123.png]]"
            fixed = fix_obsidian_embeds(md, d)
            self.assertEqual(fixed, "![[_attachments/note_1_abc123.png]]")


class TestEmptyMetrics(unittest.TestCase):
    def test_skipped_flag(self):
        m = empty_sync_metrics()
        self.assertTrue(m["skipped"])
        self.assertEqual(m["criadas"], 0)


if __name__ == "__main__":
    unittest.main()