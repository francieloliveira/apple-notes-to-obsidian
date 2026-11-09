#!/usr/bin/env python3
"""Resume de checkpoint e métricas de sync sem pendência.

Não abre o Notes e não escreve no vault real: os caminhos de estado
são redirecionados para um diretório temporário e o AppleScript é mockado.
"""

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import notes_to_obsidian as nto
from utils import save_json


_PATH_NAMES = (
    "STATE_DIR",
    "STATE_FILE",
    "IDS_FILE",
    "DIRTY_FILE",
    "CHECKPOINT_FILE",
    "METRICS_FILE",
    "PATHS_FILE",
    "LOG_FILE",
    "PROGRESS_FILE",
    "VAULT_PATH",
    "CHECKPOINT_EVERY",
)


class SyncHarness(unittest.TestCase):
    def setUp(self):
        self._orig = {name: getattr(nto, name) for name in _PATH_NAMES}
        self._orig_args = nto.ARGS
        self._orig_notes = nto._notes_was_running
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        state = root / "state"
        vault = root / "vault"
        state.mkdir()
        vault.mkdir()
        nto.STATE_DIR = str(state)
        nto.STATE_FILE = str(state / "state.json")
        nto.IDS_FILE = str(state / "ids.json")
        nto.DIRTY_FILE = str(state / "dirty.json")
        nto.CHECKPOINT_FILE = str(state / "sync_checkpoint.json")
        nto.METRICS_FILE = str(state / "metrics.json")
        nto.PATHS_FILE = str(state / "paths.json")
        nto.LOG_FILE = str(state / "sync.log")
        nto.PROGRESS_FILE = str(state / "progress.json")
        nto.VAULT_PATH = str(vault)
        nto.CHECKPOINT_EVERY = 1
        nto.ARGS = argparse.Namespace(dry_run=False, full=False, verbose=True)
        nto._notes_was_running = True
        self.vault = vault

    def tearDown(self):
        for name, value in self._orig.items():
            setattr(nto, name, value)
        nto.ARGS = self._orig_args
        nto._notes_was_running = self._orig_notes

    def _log_text(self) -> str:
        path = Path(nto.LOG_FILE)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")


class TestCheckpointResume(SyncHarness):
    def test_mid_save_reload_skips_notes_already_in_state(self):
        """Save no meio e recarga: o que já entrou no state não é reprocessado.

        Uma nota que já estava no state com data antiga continua pendente
        e tem de ser gravada de novo. Só o done desta sessão é pulado.
        """
        note_done = "note-done"
        note_changed = "note-changed"
        note_fresh = "note-fresh"
        folder_id = "folder-1"
        old_date = "segunda, 1 de janeiro de 2024 10:00:00"
        new_date = "terca, 2 de janeiro de 2024 11:00:00"
        save_json(nto.STATE_FILE, {note_changed: nto.normalize_date(old_date)})

        meta = [
            (note_done, "Alpha", folder_id, new_date),
            (note_changed, "Beta", folder_id, new_date),
            (note_fresh, "Gamma", folder_id, new_date),
        ]
        fetched = []
        writes = []
        phase = {"run": 1}

        def fake_fetch(pending, tree):
            fetched.append([n[0] for n in pending])
            return {n[0]: ("<p>ok</p>", n[3], []) for n in pending}

        def fake_write(title, segments, body_html, mod_date, note_id, paths_map, tags=None):
            if phase["run"] == 1 and writes:
                raise KeyboardInterrupt
            writes.append(note_id)
            dest = self.vault / f"{note_id}.md"
            return dest

        with patch.object(nto, "notes_db_changed", return_value=True), \
             patch.object(nto, "ensure_notes_running"), \
             patch.object(nto, "quit_notes_if_we_opened"), \
             patch.object(nto, "build_folder_tree", return_value={folder_id: ["Inbox"]}), \
             patch.object(nto, "list_meta", return_value=meta), \
             patch.object(nto, "fetch_needed", side_effect=fake_fetch), \
             patch.object(nto, "write_note", side_effect=fake_write):
            with self.assertRaises(KeyboardInterrupt):
                nto.sync()

            ckpt_path = Path(nto.CHECKPOINT_FILE)
            self.assertTrue(ckpt_path.exists(), "checkpoint não foi gravado no meio do sync")
            ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(ckpt["pending_ids"]),
                {note_done, note_changed, note_fresh},
            )
            self.assertEqual(ckpt["done_ids"], [note_done])
            self.assertIn(note_done, ckpt.get("state", {}))
            self.assertNotIn(note_changed, ckpt["done_ids"])

            phase["run"] = 2
            fetched.clear()
            writes.clear()
            ok = nto.sync()

        self.assertTrue(ok)
        self.assertIn("Retomando checkpoint", self._log_text())
        self.assertNotIn("Checkpoint inválido", self._log_text())
        self.assertEqual(len(fetched), 1)
        self.assertNotIn(note_done, fetched[0])
        self.assertIn(note_changed, fetched[0])
        self.assertIn(note_fresh, fetched[0])
        self.assertNotIn(note_done, writes)
        self.assertIn(note_changed, writes)
        self.assertIn(note_fresh, writes)

    def test_ids_that_appear_or_disappear_invalidate_checkpoint(self):
        """Id novo ou ausente invalida, como antes. Não retoma um conjunto diferente."""
        folder_id = "folder-1"
        date = "quinta, 4 de janeiro de 2024 09:00:00"
        base = [
            ("note-a", "Alpha", folder_id, date),
            ("note-b", "Beta", folder_id, date),
        ]
        writes = []
        phase = {"run": 1, "meta": list(base)}

        def fake_fetch(pending, tree):
            return {n[0]: ("<p>ok</p>", n[3], []) for n in pending}

        def fake_write(title, segments, body_html, mod_date, note_id, paths_map, tags=None):
            if phase["run"] == 1 and writes:
                raise KeyboardInterrupt
            writes.append(note_id)
            return self.vault / f"{note_id}.md"

        def current_meta():
            return list(phase["meta"])

        with patch.object(nto, "notes_db_changed", return_value=True), \
             patch.object(nto, "ensure_notes_running"), \
             patch.object(nto, "quit_notes_if_we_opened"), \
             patch.object(nto, "build_folder_tree", return_value={folder_id: ["Inbox"]}), \
             patch.object(nto, "list_meta", side_effect=current_meta), \
             patch.object(nto, "fetch_needed", side_effect=fake_fetch), \
             patch.object(nto, "write_note", side_effect=fake_write):
            with self.assertRaises(KeyboardInterrupt):
                nto.sync()

            phase["run"] = 2
            phase["meta"] = base + [("note-c", "Gamma", folder_id, date)]
            writes.clear()
            nto.sync()
            self.assertIn("Checkpoint inválido", self._log_text())
            self.assertIn("note-a", writes)

            # Nota que sumiu: o pendente atual não é mais {a, b}.
            phase["run"] = 3
            phase["meta"] = [
                ("note-a", "Alpha", folder_id, date),
                ("note-c", "Gamma", folder_id, date),
            ]
            Path(nto.LOG_FILE).write_text("", encoding="utf-8")
            writes.clear()
            save_json(nto.STATE_FILE, {})
            save_json(nto.CHECKPOINT_FILE, {
                "pending_ids": ["note-a", "note-b"],
                "done_ids": ["note-a"],
                "state": {"note-a": nto.normalize_date(date)},
                "ids": {"note-a": "note-a"},
                "paths": {},
                "dirty_paths": [],
                "created": 1,
                "updated": 0,
            })
            nto.sync()

        self.assertIn("Checkpoint inválido", self._log_text())
        self.assertIn("note-a", writes)


class TestNoPendingMetrics(SyncHarness):
    def test_no_pending_rewrites_metrics_with_skipped_zeros(self):
        """Path sem pendência reescreve metrics. Não reaproveita o aviso anterior."""
        date = "quarta, 3 de janeiro de 2024 12:00:00"
        save_json(nto.STATE_FILE, {"n1": nto.normalize_date(date)})
        save_json(nto.METRICS_FILE, {
            "generated_at": "2000-01-01T00:00:00",
            "criadas": 4,
            "atualizadas": 2,
            "protegidas": 1,
            "bloqueadas": 3,
            "erros": 1,
            "skipped": False,
        })
        meta = [("n1", "Alpha", "folder-1", date)]

        with patch.object(nto, "notes_db_changed", return_value=True), \
             patch.object(nto, "ensure_notes_running"), \
             patch.object(nto, "quit_notes_if_we_opened"), \
             patch.object(nto, "build_folder_tree", return_value={"folder-1": ["Inbox"]}), \
             patch.object(nto, "list_meta", return_value=meta), \
             patch.object(nto, "fetch_needed") as fetch, \
             patch.object(nto, "write_note") as write:
            ok = nto.sync()

        self.assertTrue(ok)
        self.assertIn("Tudo atualizado", self._log_text())
        fetch.assert_not_called()
        write.assert_not_called()
        metrics = json.loads(Path(nto.METRICS_FILE).read_text(encoding="utf-8"))
        self.assertTrue(metrics["skipped"])
        self.assertEqual(metrics["criadas"], 0)
        self.assertEqual(metrics["atualizadas"], 0)
        self.assertEqual(metrics["protegidas"], 0)
        self.assertEqual(metrics["erros"], 0)
        self.assertEqual(metrics["bloqueadas"], 0)
        self.assertNotEqual(metrics["generated_at"], "2000-01-01T00:00:00")


class TestSyncMetricsSchema(SyncHarness):
    def _assert_schema(self, metrics):
        for key in ("criadas", "atualizadas", "protegidas", "erros", "skipped", "bloqueadas"):
            self.assertIn(key, metrics)

    def test_real_sync_writes_skipped_false(self):
        date = "sexta, 5 de janeiro de 2024 08:00:00"
        meta = [("n1", "Alpha", "folder-1", date)]

        def fake_fetch(pending, tree):
            return {n[0]: ("<p>ok</p>", n[3], []) for n in pending}

        def fake_write(title, segments, body_html, mod_date, note_id, paths_map, tags=None):
            return self.vault / f"{note_id}.md"

        with patch.object(nto, "notes_db_changed", return_value=True), \
             patch.object(nto, "ensure_notes_running"), \
             patch.object(nto, "quit_notes_if_we_opened"), \
             patch.object(nto, "build_folder_tree", return_value={"folder-1": ["Inbox"]}), \
             patch.object(nto, "list_meta", return_value=meta), \
             patch.object(nto, "fetch_needed", side_effect=fake_fetch), \
             patch.object(nto, "write_note", side_effect=fake_write):
            ok = nto.sync()

        self.assertTrue(ok)
        metrics = json.loads(Path(nto.METRICS_FILE).read_text(encoding="utf-8"))
        self._assert_schema(metrics)
        self.assertFalse(metrics["skipped"])
        self.assertEqual(metrics["criadas"], 1)
        self.assertEqual(metrics["bloqueadas"], 0)

    def test_checkpoint_finish_uses_metrics_schema(self):
        date = "sabado, 6 de janeiro de 2024 08:00:00"
        note_id = "n-done"
        save_json(nto.CHECKPOINT_FILE, {
            "pending_ids": [note_id],
            "done_ids": [note_id],
            "state": {note_id: nto.normalize_date(date)},
            "ids": {note_id: note_id},
            "paths": {},
            "dirty_paths": ["Inbox/Alpha.md"],
            "created": 2,
            "updated": 1,
        })
        meta = [(note_id, "Alpha", "folder-1", date)]

        with patch.object(nto, "notes_db_changed", return_value=True), \
             patch.object(nto, "ensure_notes_running"), \
             patch.object(nto, "quit_notes_if_we_opened"), \
             patch.object(nto, "build_folder_tree", return_value={"folder-1": ["Inbox"]}), \
             patch.object(nto, "list_meta", return_value=meta), \
             patch.object(nto, "fetch_needed") as fetch, \
             patch.object(nto, "write_note") as write:
            ok = nto.sync()

        self.assertTrue(ok)
        self.assertIn("já gravadas", self._log_text())
        fetch.assert_not_called()
        write.assert_not_called()
        metrics = json.loads(Path(nto.METRICS_FILE).read_text(encoding="utf-8"))
        self._assert_schema(metrics)
        self.assertFalse(metrics["skipped"])
        self.assertEqual(metrics["criadas"], 2)
        self.assertEqual(metrics["atualizadas"], 1)
        self.assertEqual(metrics["bloqueadas"], 0)
        self.assertEqual(metrics["protegidas"], 0)
        self.assertEqual(metrics["erros"], 0)


