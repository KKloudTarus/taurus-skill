#!/usr/bin/env python3
"""Regression coverage for Codex's cmd.exe hook launch boundaries."""

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv


REPO = Path(__file__).resolve().parents[1]
GENERATOR = REPO / "hooks" / "windows-hook-command.py"


def command_for(python, guard):
    return subprocess.check_output(
        [sys.executable, str(GENERATOR), str(python), str(guard)],
        text=True, encoding="utf-8",
    ).strip()


class TestWindowsCommand(unittest.TestCase):
    def test_outer_command_contains_no_shell_sensitive_path_characters(self):
        python = r"C:\Python space's ‘’‚‛ & %PATH% !\python.exe"
        guard = r"C:\Taurus space's ‘’‚‛ & %PATH% !\guard-git.py"
        command = command_for(python, guard)
        prefix, encoded = command.rsplit(" ", 1)
        self.assertEqual(
            prefix, r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
                    " -NoLogo -NoProfile -NonInteractive -EncodedCommand"
        )
        script = base64.b64decode(encoded, validate=True).decode("utf-16-le")
        for path in (python, guard):
            escaped = path
            for quote in "'‘’‚‛":
                escaped = escaped.replace(quote, quote * 2)
            self.assertIn(escaped, script)
        self.assertEqual(command, command_for(python, guard))

    @unittest.skipIf(os.name == "nt", "MSYS wiring fixture uses POSIX symlinks; Windows runs native launch tests")
    def test_installer_generates_and_removes_windows_wiring(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / "bin"
            binary.mkdir()
            cygpath = binary / "cygpath"
            cygpath.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print(\"C:\\\\fixture space's\\\\\" + sys.argv[2].rsplit('/', 1)[-1])\n",
                encoding="utf-8",
            )
            cygpath.chmod(0o755)
            env = {**os.environ, "HOME": str(root / "home"),
                   "CODEX_HOME": str(root / "codex"),
                   "CLAUDE_CONFIG_DIR": str(root / "claude"),
                   "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
            args = ["bash", str(REPO / "install.sh"), "--target", "codex",
                    "--no-gitignore", "--no-githooks"]
            subprocess.run(args, env=env, check=True, capture_output=True)
            hooks = root / "codex" / "hooks.json"
            original = hooks.read_bytes()
            doc = json.loads(original)
            handler = doc["hooks"]["PreToolUse"][0]["hooks"][0]
            self.assertEqual(
                handler["commandWindows"],
                command_for(r"C:\fixture space's\python3", r"C:\fixture space's\guard-git.py"),
            )
            subprocess.run(args, env=env, check=True, capture_output=True)
            self.assertEqual(hooks.read_bytes(), original)
            notes = root / "codex" / "AGENTS.md"
            with notes.open("a", encoding="utf-8") as stream:
                stream.write("\n\nUser notes after the managed block.\n")
            before = notes.read_bytes()
            subprocess.run(args, env=env, check=True, capture_output=True)
            self.assertEqual(notes.read_bytes(), before)
            subprocess.run(args + ["--uninstall"], env=env, check=True, capture_output=True)
            self.assertNotIn("PreToolUse", json.loads(hooks.read_bytes()).get("hooks", {}))


@unittest.skipUnless(os.name == "nt", "requires the native Windows cmd.exe runtime")
class TestNativeWindowsHook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="taurus windows ")
        cls.root = Path(cls.temp.name)
        cls.install = cls.root / "space's ‘’‚‛ é & %PATH% !"
        cls.install.mkdir()
        cls.venv = cls.install / "Python runtime"
        venv.create(cls.venv, with_pip=False)
        cls.python = cls.venv / "Scripts" / "python.exe"
        cls.hooks = cls.install / "hooks"
        shutil.copytree(REPO / "hooks", cls.hooks, ignore=shutil.ignore_patterns("__pycache__"))
        cls.guard = cls.hooks / "guard-git.py"
        cls.echo = cls.hooks / "payload echo.py"
        cls.echo.write_text(
            "import json, sys\n"
            "payload = json.load(sys.stdin)\n"
            "print(json.dumps(payload, ensure_ascii=True))\n"
            "sys.exit(payload['exit_code'])\n",
            encoding="utf-8",
        )
        cls.repo = cls.root / "project space"
        cls.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(cls.repo)], check=True)
        cls.subdir = cls.repo / "subdir"
        cls.subdir.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def launch(self, command, payload, cwd, boundary="argv"):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        if boundary == "argv":
            # Older runners apply MSVC argv quoting to the entire /C argument.
            args = [comspec, "/D", "/C", command]
        else:
            # Current runners wrap the hook command in a raw command-line argument.
            args = subprocess.list2cmdline([comspec, "/D", "/C"]) + ' "' + command + '"'
        return subprocess.run(
            args, input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, timeout=30,
        )

    def test_quoted_python_command_reproduces_the_original_failure(self):
        result = self.launch(
            f'"{sys.executable}" "{self.guard}"', {}, self.repo
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b"BLOCKED by taurus", result.stderr)

    def test_payload_and_exit_status_survive_both_cmd_boundaries(self):
        command = command_for(self.python, self.echo)
        for boundary in ("argv", "raw"):
            for exit_code in (0, 2, 7):
                with self.subTest(boundary=boundary, exit_code=exit_code):
                    payload = {"text": "Tiếng Việt 😀\n' & %PATH% !" * 4096,
                               "exit_code": exit_code}
                    result = self.launch(command, payload, self.subdir, boundary)
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    self.assertEqual(json.loads(result.stdout), payload)

    def test_real_guard_allows_reads_and_blocks_writes_from_root_and_subdir(self):
        command = command_for(self.python, self.guard)
        for boundary in ("argv", "raw"):
            for cwd in (self.repo, self.subdir):
                for tool in ("Bash", "shell"):
                    for text, expected in (("git status --short", 0),
                                           ("git commit -m bad", 2),
                                           ("git add AGENTS.md", 2)):
                        with self.subTest(boundary=boundary, cwd=cwd, tool=tool, text=text):
                            payload = {"tool_name": tool, "cwd": str(cwd),
                                       "tool_input": {"command": text}}
                            result = self.launch(command, payload, cwd, boundary)
                            self.assertEqual(result.returncode, expected, result.stderr)
                            if expected == 2:
                                self.assertIn(b"BLOCKED by taurus", result.stderr)
                                self.assertNotIn(b"CLIXML", result.stderr)

    def test_missing_interpreter_is_a_launcher_error(self):
        result = self.launch(
            command_for(self.install / "missing.exe", self.guard), {}, self.repo
        )
        self.assertNotEqual(result.returncode, 0)

    def test_project_local_powershell_cannot_replace_the_system_launcher(self):
        shadow = self.repo / "powershell.exe"
        shutil.copyfile(os.environ.get("COMSPEC", "cmd.exe"), shadow)
        try:
            command = command_for(self.python, self.guard)
            for boundary in ("argv", "raw"):
                with self.subTest(boundary=boundary):
                    payload = {"tool_name": "Bash", "cwd": str(self.repo),
                               "tool_input": {"command": "git commit -m bad"}}
                    result = self.launch(command, payload, self.repo, boundary)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn(b"BLOCKED by taurus", result.stderr)
        finally:
            shadow.unlink()


if __name__ == "__main__":
    unittest.main()
