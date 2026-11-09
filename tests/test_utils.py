#!/usr/bin/env python3
"""Testes unitários do VaultAI."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notes_to_obsidian import normalize_date
from utils import (
    extract_note_id, empty_sync_metrics, merge_aliases,
    sanitize_title_for_filename, unique_filename, url_to_filename_slug,
    fix_obsidian_embeds, is_secret_note, remove_secret_from_vault,
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
        self.assertEqual(m.get("bloqueadas", 0), 0)


class TestSecretsBlocklist(unittest.TestCase):
    """Secrets ficam só no Apple Notes — nunca no vault."""

    def test_blocks_senha_title(self):
        ok, reason = is_secret_note("Senha hotmail", enabled=True)
        self.assertTrue(ok)
        self.assertIn("título", reason)

    def test_blocks_api_key_title(self):
        ok, _ = is_secret_note("API key", enabled=True)
        self.assertTrue(ok)

    def test_blocks_folder_senhas(self):
        ok, reason = is_secret_note("lista wifi", "", ["Pessoal", "Senhas"], enabled=True)
        self.assertTrue(ok)
        self.assertIn("pasta", reason)

    def test_allows_passwordless_howto(self):
        ok, _ = is_secret_note("Passwordless ssh", enabled=True)
        self.assertFalse(ok)

    def test_allows_windows_senha_howto(self):
        ok, _ = is_secret_note("Mudar senha usuário Windows 10", enabled=True)
        self.assertFalse(ok)

    def test_blocks_sk_in_body(self):
        ok, reason = is_secret_note(
            "config local",
            "export ANTHROPIC_API_KEY=sk-abcdefghijklmnopqrstuv",
            enabled=True,
        )
        self.assertTrue(ok)
        self.assertIn("conteúdo", reason)

    def test_blocks_akia_in_body(self):
        ok, _ = is_secret_note(
            "aws setup",
            "access key AKIAIOSFODNN7EXAMPLE",
            enabled=True,
        )
        self.assertTrue(ok)

    def test_disabled_flag(self):
        ok, _ = is_secret_note("Senha x", enabled=False)
        self.assertFalse(ok)

    def test_normal_note_passes(self):
        ok, _ = is_secret_note(
            "INC QR code validação",
            "Ajuste no fluxo de scan do totem.",
            ["Clientes", "PETROBRAS"],
            enabled=True,
        )
        self.assertFalse(ok)


class TestRemoveSecretFromVault(unittest.TestCase):
    def test_prefix_stem_does_not_delete_other_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            folder = vault / "Senhas"
            att = folder / "_attachments"
            att.mkdir(parents=True)

            # Stem "Senha" is a prefix of the other note's attachment, and
            # "Senha" also appears inside a third filename. Neither is cited.
            secret = folder / "Senha.md"
            secret.write_text(
                "---\n"
                "source: Apple Notes\n"
                "---\n\n"
                + ("x" * 500)
                + "\n![[_attachments/wifi_1_ab12cd.png]]\n"
                + "![[token_2_cd34ef.png]]\n",
                encoding="utf-8",
            )
            referenced_prefixed = att / "wifi_1_ab12cd.png"
            referenced_bare = att / "token_2_cd34ef.png"
            prefix_other = att / "Senha_wifi_1_ffffff.png"
            substring_other = att / "notes_Senha_2_aaaaaa.png"
            for path, payload in (
                (referenced_prefixed, b"ref-prefix"),
                (referenced_bare, b"ref-bare"),
                (prefix_other, b"other-prefix"),
                (substring_other, b"other-substr"),
            ):
                path.write_bytes(payload)

            paths = {"n1": "Senhas/Senha.md"}
            removed = remove_secret_from_vault("n1", paths, vault)
            self.assertEqual(removed, "Senhas/Senha.md")
            self.assertNotIn("n1", paths)
            self.assertFalse(secret.exists())
            self.assertFalse(referenced_prefixed.exists())
            self.assertFalse(referenced_bare.exists())
            self.assertEqual(prefix_other.read_bytes(), b"other-prefix")
            self.assertEqual(substring_other.read_bytes(), b"other-substr")

            stuck = folder / "Token.md"
            stuck.write_text(
                "---\nsource: Apple Notes\n---\n\nsegredo\n",
                encoding="utf-8",
            )
            paths_stuck = {"n2": "Senhas/Token.md"}
            real_unlink = Path.unlink

            def unlink(self, *args, **kwargs):
                if self == stuck:
                    raise OSError("unlink failed")
                return real_unlink(self, *args, **kwargs)

            with mock.patch.object(Path, "unlink", unlink):
                failed = remove_secret_from_vault("n2", paths_stuck, vault)
            self.assertIs(failed, False)
            self.assertEqual(paths_stuck, {"n2": "Senhas/Token.md"})
            self.assertTrue(stuck.is_file())


if __name__ == "__main__":
    unittest.main()