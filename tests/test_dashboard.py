#!/usr/bin/env python3
"""Dashboard compacto: lê os JSON do pipeline e não apaga os hooks."""

import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vaultai_dashboard as dash


FIXTURE_METRICS = {
    "criadas": 17,
    "atualizadas": 23,
    "erros": 5,
    "bloqueadas": 9,
    "skipped": False,
    "protegidas": 2,
}


def _write(directory: Path, name: str, payload) -> None:
    (directory / name).write_text(
        json.dumps(payload), encoding="utf-8",
    )


class TestSnapshot(unittest.TestCase):
    def test_fixture_numbers_not_hardcoded_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            _write(state, "metrics.json", FIXTURE_METRICS)
            _write(state, "status.json", {
                "state": "ok",
                "message": "fixture-ok",
                "updated_at": "2026-11-09T12:00:00",
                "metrics": {"criadas": 0, "atualizadas": 0, "erros": 0, "bloqueadas": 0},
            })
            _write(state, "organize_metrics.json", {
                "linkadas": 11,
                "mocs": 4,
                "lixo": 2,
            })
            _write(state, "progress.json", {"current": 6, "total": 20, "criadas": 1})

            snap = dash.read_snapshot(state)

        self.assertEqual(snap["metrics"]["criadas"], 17)
        self.assertEqual(snap["metrics"]["atualizadas"], 23)
        self.assertEqual(snap["metrics"]["erros"], 5)
        self.assertEqual(snap["metrics"]["bloqueadas"], 9)
        self.assertIs(snap["metrics"]["skipped"], False)
        self.assertEqual(snap["status"]["message"], "fixture-ok")
        self.assertEqual(snap["organize"]["linkadas"], 11)
        self.assertEqual(snap["progress"]["current"], 6)

        sync_line = dash.format_sync_line(snap["metrics"])
        for number in ("17", "23", "5", "9"):
            self.assertIn(number, sync_line)
        self.assertNotIn("criadas: 0", sync_line)
        self.assertIn("skipped", sync_line.lower())

        organize_line = dash.format_organize_line(snap["organize"])
        self.assertIn("11", organize_line)
        self.assertIn("4", organize_line)
        self.assertEqual(organize_line.count("\n"), 0)

        progress_line = dash.format_progress_line(snap["progress"])
        self.assertIn("6", progress_line)
        self.assertIn("20", progress_line)

    def test_missing_progress_is_absent(self):
        self.assertIsNone(dash.format_progress_line({}))
        self.assertIsNone(dash.format_progress_line(None))


class TestHooks(unittest.TestCase):
    def test_pause_calls_hook_and_keeps_it(self):
        calls = []

        def hook():
            calls.append("pause")

        app = dash.DashboardActions(on_pause=hook, on_resume=lambda: None)
        app.pause()
        app.pause()
        self.assertIs(app.on_pause, hook)
        self.assertEqual(calls, ["pause", "pause"])

    def test_resume_calls_hook_and_keeps_it(self):
        calls = []

        def hook():
            calls.append("resume")

        app = dash.DashboardActions(on_pause=lambda: None, on_resume=hook)
        app.resume()
        self.assertIs(app.on_resume, hook)
        self.assertEqual(calls, ["resume"])

    def test_pause_does_not_assign_call_result(self):
        def hook():
            return "wiped"

        app = dash.DashboardActions(on_pause=hook, on_resume=lambda: None)
        app.pause()
        self.assertIs(app.on_pause, hook)
        self.assertTrue(callable(app.on_pause))

    def test_default_pause_marks_file_without_wiping_hook(self):
        calls = []

        def launchctl(*args, **kwargs):
            calls.append(args)
            return mock.Mock(returncode=0)

        with tempfile.TemporaryDirectory() as tmp:
            app = dash.DashboardActions(state_dir=tmp, launchctl=launchctl)
            hook = app.on_pause
            resume_hook = app.on_resume
            app.pause()
            self.assertIs(app.on_pause, hook)
            self.assertTrue((Path(tmp) / "sync_paused").is_file())
            app.resume()
            self.assertIs(app.on_resume, resume_hook)
            self.assertFalse((Path(tmp) / "sync_paused").exists())
        self.assertTrue(calls)
        app = dash.DashboardActions()
        self.assertFalse(hasattr(app, "on_save_config"))
        save = getattr(app, "save", None)
        if save is not None:
            save()

    def test_launchctl_nonzero_does_not_create_or_remove_sync_paused(self):
        errors = []

        def launchctl(*args, **kwargs):
            return mock.Mock(returncode=1)

        with tempfile.TemporaryDirectory() as tmp:
            paused = Path(tmp) / "sync_paused"
            app = dash.DashboardActions(
                state_dir=tmp,
                launchctl=launchctl,
                on_error=errors.append,
            )
            app.pause()
            self.assertFalse(paused.exists())
            paused.write_text("on", encoding="utf-8")
            app.resume()
            self.assertTrue(paused.is_file())
            self.assertEqual(paused.read_text(encoding="utf-8"), "on")
        self.assertTrue(errors)


class TestOpenLog(unittest.TestCase):
    def test_open_log_receives_absolute_path_and_textedit(self):
        seen = []

        def opener(argv, **kwargs):
            seen.append(list(argv))

        path = dash.open_log("~/.vault/pipeline.log", opener=opener)
        self.assertTrue(os.path.isabs(path))
        self.assertFalse(path.startswith("~"))
        self.assertNotIn("~/.vault", path)
        self.assertEqual(seen[0][0], "open")
        self.assertIn("TextEdit", seen[0])
        self.assertNotIn("Xcode", seen[0])
        self.assertEqual(seen[0][-1], path)
        self.assertNotEqual(seen[0][-1], "~/.vault/pipeline.log")


class TestColors(unittest.TestCase):
    def test_idle_is_not_error_and_pause_is_not_ok(self):
        idle = dash.state_color("idle").lower()
        error = dash.state_color("erro").lower()
        pause = dash.state_color("pausa").lower()
        ok = dash.state_color("ok").lower()
        syncing = dash.state_color("sincronizando").lower()
        self.assertNotEqual(idle, error)
        self.assertNotEqual(pause, ok)
        self.assertEqual(len({idle, error, pause, ok, syncing}), 5)

    def test_paused_file_wins_over_ok(self):
        state = dash.display_state({"state": "ok"}, paused=True)
        self.assertEqual(state, "pausa")
        self.assertNotEqual(dash.state_color(state), dash.state_color("ok"))

    def test_running_is_sincronizando(self):
        self.assertEqual(
            dash.display_state({"state": "running"}, paused=False),
            "sincronizando",
        )


class TestSyncNow(unittest.TestCase):
    def test_pipeline_error_is_shown_and_does_not_raise(self):
        shown = []

        def boom():
            raise RuntimeError("pipeline caiu")

        app = dash.DashboardActions(pipeline_runner=boom, on_error=shown.append)
        app.sync_now()
        self.assertTrue(shown)
        self.assertIn("pipeline caiu", shown[0])

    def test_nonzero_exit_is_shown(self):
        shown = []
        app = dash.DashboardActions(
            pipeline_runner=lambda: 2,
            on_error=shown.append,
        )
        app.sync_now()
        self.assertTrue(shown)
        self.assertIn("2", shown[0])


class TestAppBundle(unittest.TestCase):
    def test_generated_app_has_one_id_and_execs_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "vaultai_dashboard.py"
            script.write_text("print('janela')\n", encoding="utf-8")
            app = Path(tmp) / "VaultAI.app"
            dash.ensure_app(
                app_path=app,
                python="/usr/bin/python3",
                script=script,
            )
            plist = (app / "Contents" / "Info.plist").read_text(encoding="utf-8")
            executable = (app / "Contents" / "MacOS" / "VaultAI").read_text(encoding="utf-8")
            copied = list((app / "Contents" / "MacOS").glob("*.py"))

        forbidden_desktop = "com.vaultai." + "desktop"
        forbidden_launcher = "com.vaultai." + "launcher"
        self.assertIn(dash.BUNDLE_ID, plist)
        self.assertNotIn(forbidden_desktop, plist)
        self.assertNotIn(forbidden_launcher, plist)
        self.assertEqual(plist.count("CFBundleIdentifier"), 1)
        self.assertIn("13.0", plist)
        self.assertIn(str(script), executable)
        self.assertIn("/usr/bin/python3", executable)
        self.assertEqual(copied, [])

    def test_regenerate_removes_old_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "vaultai_dashboard.py"
            script.write_text("print('janela')\n", encoding="utf-8")
            app = Path(tmp) / "VaultAI.app"
            macos = app / "Contents" / "MacOS"
            macos.mkdir(parents=True)
            (macos / "launcher").write_text("#!/bin/bash\necho old\n", encoding="utf-8")
            dash.ensure_app(app_path=app, python="/usr/bin/python3", script=script)
            names = sorted(p.name for p in macos.iterdir())
        self.assertEqual(names, ["VaultAI"])

    def test_bundle_rejects_venv_and_dataless_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            venv_python = root / ".venv" / "bin" / "python3"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("#!/bin/sh\necho no\n", encoding="utf-8")
            venv_python.chmod(0o755)
            script = root / "vaultai_dashboard.py"
            script.write_text("print('janela')\n", encoding="utf-8")
            app = root / "VaultAI.app"
            dash.ensure_app(app_path=app, python=str(venv_python), script=script)
            executable = (app / "Contents" / "MacOS" / "VaultAI").read_text(encoding="utf-8")
            plist = (app / "Contents" / "Info.plist").read_text(encoding="utf-8")

        self.assertNotIn(".venv", executable)
        self.assertNotIn(str(venv_python), executable)
        self.assertIn("<string>VaultAI</string>", plist)
        command = executable.split("exec ", 1)[1].strip()
        chosen = shlex.split(command)[0]
        self.assertFalse(dash._under_venv(chosen))
        self.assertTrue(dash._imports_site(chosen))

    def test_dataless_is_not_empty_and_not_a_valid_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "six.py"
            path.write_bytes(b"print('not-empty')\n")
            path.chmod(0o755)
            real_open = os.open

            def boom(file, flags, *args, **kwargs):
                if os.fspath(file) == str(path):
                    raise OSError(11, "Resource deadlock avoided")
                return real_open(file, flags, *args, **kwargs)

            with mock.patch("os.open", boom):
                self.assertTrue(dash.is_dataless(path))
                self.assertFalse(dash.interpreter_ready(str(path)))
            self.assertGreater(path.stat().st_size, 0)
            self.assertTrue(os.path.isfile(path))

    def test_dataless_flag_rejects_without_opening(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "python3"
            path.write_bytes(b"#!/bin/sh\n")
            real_stat = os.stat

            def fake_stat(target, *args, **kwargs):
                st = real_stat(target, *args, **kwargs)
                if os.fspath(target) == str(path):
                    return type("ST", (), {
                        "st_mode": st.st_mode,
                        "st_flags": dash._SF_DATALESS,
                        "st_size": st.st_size,
                    })()
                return st

            def boom(*args, **kwargs):
                raise AssertionError("não abre dataless")

            with mock.patch("os.stat", fake_stat), mock.patch("os.open", boom):
                self.assertTrue(dash.is_dataless(path))
                self.assertFalse(dash.interpreter_ready(str(path)))

    def test_icloud_project_venv_stays_outside_the_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            project = parent / "repo"
            project.mkdir()

            def names(path):
                if os.fspath(path) == str(parent):
                    return {"com.apple.file-provider-domain-id"}
                return set()

            with mock.patch.object(dash, "_xattr_names", side_effect=names):
                venv = dash.pipeline_venv_dir(str(project))
                self.assertTrue(dash.path_on_icloud(str(project)))
            self.assertFalse(str(venv).startswith(str(project)))
            self.assertNotIn(".venv", Path(venv).parts)

            with mock.patch.object(dash, "_xattr_names", return_value=set()):
                inside = dash.pipeline_venv_dir(str(project))
            self.assertEqual(inside, str(project / ".venv"))

    def test_agent_python_is_pipeline_venv_not_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "repo"
            project.mkdir()
            py = Path(tmp) / "venv" / "bin" / "python3"
            py.parent.mkdir(parents=True)
            py.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.object(dash, "pipeline_venv_dir", return_value=str(Path(tmp) / "venv")), \
                 mock.patch.object(dash, "interpreter_ready", return_value=True), \
                 mock.patch.object(dash, "_imports_site", return_value=True):
                chosen = dash.agent_python(str(project))
        self.assertEqual(chosen, str(py))
        self.assertNotEqual(chosen, "/usr/bin/python3")
        self.assertNotIn(".venv", Path(chosen).parts)

    def test_agent_python_refuses_unready_venv(self):
        with mock.patch.object(dash, "pipeline_venv_dir", return_value="/tmp/vaultai-no-venv"), \
             mock.patch.object(dash, "interpreter_ready", return_value=False):
            with self.assertRaises(SystemExit):
                dash.agent_python("/tmp/repo")


class TestWindow(unittest.TestCase):
    def _window(self, state: Path, **kwargs):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        return dash.VaultWindow(master=root, state_dir=state, **kwargs)

    def test_window_shows_fixture_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            _write(state, "metrics.json", FIXTURE_METRICS)
            _write(state, "status.json", {
                "state": "ok",
                "message": "fixture-ok",
                "updated_at": "2026-11-09T12:00:00",
                "metrics": {"criadas": 0},
            })
            _write(state, "organize_metrics.json", {"linkadas": 11, "mocs": 4, "lixo": 2})
            _write(state, "progress.json", {"current": 6, "total": 20})
            window = self._window(state, log_path=str(state / "pipeline.log"))
            text = window.visible_text()
            self.assertEqual(window.root.minsize(), (420, 560))
            self.assertEqual(dash.WINDOW_SIZE, "420x560")
            self.assertEqual(window.root.cget("bg"), dash.BG)
            self.assertNotEqual(window.root.cget("bg").lower(), "#ffffff")

        for number in ("17", "23", "5", "9", "11", "6", "20"):
            self.assertIn(number, text)
        self.assertIn("fixture-ok", text)
        self.assertNotIn("criadas: 0", text)
        self.assertNotIn("Segoe", text)
        self.assertNotIn("Consolas", text)
        self._assert_one_manager(window.root)

    def test_pause_button_keeps_callback_and_log_button_is_absolute(self):
        seen = []

        def opener(argv, **kwargs):
            seen.append(list(argv))

        calls = []

        def hook():
            calls.append("pause")
            return "nao-atribuir"

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            _write(state, "metrics.json", FIXTURE_METRICS)
            _write(state, "status.json", {"state": "idle", "message": ""})
            window = self._window(
                state,
                log_path="~/.vault/pipeline.log",
                on_pause=hook,
                opener=opener,
            )
            self._button(window, "Pausar").invoke()
            self._button(window, "Abrir log").invoke()
            self.assertIs(window.actions.on_pause, hook)
            self.assertEqual(calls, ["pause"])
            self.assertTrue(os.path.isabs(seen[0][-1]))
            self.assertNotIn("~", seen[0][-1])
            self.assertIn("TextEdit", seen[0])
            self.assertNotIn("Xcode", seen[0])
            idle_fg = window.state_label.cget("fg").lower()
            self.assertNotEqual(idle_fg, dash.state_color("erro").lower())

    def test_sync_error_appears_on_window(self):
        def boom():
            raise RuntimeError("pipeline caiu")

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            _write(state, "status.json", {"state": "ok", "message": ""})
            window = self._window(state, pipeline_runner=boom)
            window.actions.sync_now()
            self.assertIn("pipeline caiu", window.visible_text())
            self.assertEqual(window.state_label.cget("text"), "erro")

    def _button(self, window, label):
        found = []

        def walk(widget):
            if widget.winfo_class() == "Button" and widget.cget("text") == label:
                found.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(window.root)
        self.assertEqual(len(found), 1, label)
        return found[0]

    def _assert_one_manager(self, widget):
        children = widget.winfo_children()
        if children:
            managers = {child.winfo_manager() for child in children}
            self.assertEqual(len(managers), 1, widget)
        for child in children:
            self._assert_one_manager(child)


class TestInstallPointsAtOneApp(unittest.TestCase):
    def test_install_starts_window_and_menubar(self):
        root = Path(__file__).resolve().parent.parent
        text = (root / "install.sh").read_text(encoding="utf-8")
        forbidden_desktop = "com.vaultai." + "desktop"
        forbidden_launcher = "com.vaultai." + "launcher"
        self.assertIn("vaultai_dashboard", text)
        self.assertIn("ensure_app", text)
        self.assertIn("vault_menubar.py", text)
        self.assertNotIn(forbidden_launcher, text)
        self.assertNotIn(forbidden_desktop, text)
        loaded = [
            line for line in text.splitlines()
            if "launchctl load" in line
        ]
        self.assertTrue(any("MENUBAR_LABEL" in line for line in loaded))
        self.assertTrue(any("PIPELINE_LABEL" in line for line in loaded))
        menubar_plist = text.split('MENUBAR_LABEL}.plist" <<EOF', 1)[1].split("EOF", 1)[0]
        self.assertIn("${PYTHON}", menubar_plist)
        self.assertIn("vault_menubar.py", menubar_plist)
        self.assertNotIn("APP_PYTHON", menubar_plist)
        self.assertNotIn(".venv", menubar_plist)
        self.assertNotIn(
            'rm -f "${LAUNCHAGENTS_DIR}/${MENUBAR_LABEL}.plist"',
            text,
        )
        self.assertIn('APP_PYTHON="/usr/bin/python3"', text)
        self.assertIn("ensure_app(python=", text)
        self.assertLess(text.index("ensure_app(python="), text.index("pipeline_venv_dir"))
        for line in text.splitlines():
            if "ensure_app" in line:
                self.assertNotIn("VENV", line)
                self.assertNotIn(".venv", line)
        example = (root / "config.example.py").read_text(encoding="utf-8")
        python_bin = [
            line for line in example.splitlines() if line.startswith("PYTHON_BIN")
        ]
        self.assertEqual(len(python_bin), 1)
        self.assertNotIn(".venv", python_bin[0])
        self.assertIn("/usr/bin/python3", python_bin[0])
        menubar = (root / "vault_menubar.py").read_text(encoding="utf-8")
        self.assertIn("ensure_app(python=_WINDOW_PYTHON)", menubar)
        self.assertNotIn("os.path.isfile(PYTHON_BIN)", menubar)


if __name__ == "__main__":
    unittest.main()
