#!/usr/bin/env python3
"""Testes unitários das funções puras de organize_vault.py (Modelo A de linking)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from organize_vault import (
    add_links_section, find_links, is_lixo_by_name,
    parse_frontmatter, title_mentioned,
)


class TestTitleMentioned(unittest.TestCase):
    def test_matches_word_boundary(self):
        self.assertTrue(
            title_mentioned("falei sobre docker compose ontem", "docker compose")
        )

    def test_no_partial_match(self):
        self.assertFalse(title_mentioned("dockerfile customizado", "docker"))

    def test_ignores_titles_below_min_chars(self):
        self.assertFalse(title_mentioned("ok, feito", "ok"))


class TestParseFrontmatter(unittest.TestCase):
    def test_extracts_simple_and_list_fields(self):
        raw = (
            '---\n'
            'title: "Minha Nota"\n'
            'tags:\n'
            '  - "trabalho"\n'
            '  - "urgente"\n'
            '---\n\ncorpo da nota'
        )
        fm = parse_frontmatter(raw)
        self.assertEqual(fm["title"], "Minha Nota")
        self.assertEqual(fm["tags"], ["trabalho", "urgente"])


class TestFindLinks(unittest.TestCase):
    @staticmethod
    def _note(note_id, title, text, tags=None):
        return {
            "note_id": note_id, "title": title, "link": title,
            "text": text, "tags": tags or set(),
        }

    def test_links_by_title_mention(self):
        # "text" chega em minúsculas em collect_all_notes() — title_mentioned()
        # só normaliza o título, não o texto.
        target = self._note("b", "Projeto Alpha", "")
        source = self._note("a", "Diario", "hoje falei do projeto alpha no standup")
        links = find_links(source, {"a": source, "b": target})
        self.assertIn("Projeto Alpha", links)

    def test_links_by_shared_tags_when_no_title_mention(self):
        target = self._note("b", "Projeto Beta", "", tags={"urgente"})
        source = self._note("a", "Diario", "nada em comum aqui", tags={"urgente"})
        links = find_links(source, {"a": source, "b": target})
        self.assertIn("Projeto Beta", links)

    def test_excludes_self(self):
        source = self._note("a", "Diario", "Diario de hoje")
        links = find_links(source, {"a": source})
        self.assertEqual(links, [])


class TestAddLinksSection(unittest.TestCase):
    def test_appends_new_links(self):
        content = "# Nota\n\nConteúdo."
        updated = add_links_section(content, ["Outra Nota"])
        self.assertIn("[[Outra Nota]]", updated)

    def test_skips_link_already_present_in_body(self):
        content = "# Nota\n\nVeja [[Outra Nota]] no texto."
        updated = add_links_section(content, ["Outra Nota"])
        self.assertEqual(updated.count("[[Outra Nota]]"), 1)


class TestIsLixoByName(unittest.TestCase):
    def test_matches_default_pattern(self):
        self.assertTrue(is_lixo_by_name("Nova nota"))

    def test_normal_title_is_not_lixo(self):
        self.assertFalse(is_lixo_by_name("Reunião de projeto"))


if __name__ == "__main__":
    unittest.main()
