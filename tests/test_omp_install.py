#!/usr/bin/env python3
"""End-to-end tests for the project-scoped OMP installer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OmpInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.work = Path(self.temporary.name)
        self.source = self.work / "source"
        shutil.copytree(ROOT, self.source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.installer = self.source / "compat" / "omp" / "install.py"
        self.project = self.work / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(
        self, *arguments: str, project: Path | None = None, home: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        if home is not None:
            environment["HOME"] = str(home)
        return subprocess.run(
            [sys.executable, str(self.installer), "--project", str(project or self.project), *arguments],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )

    def install(self, project: Path | None = None, home: Path | None = None) -> None:
        result = self.invoke(project=project, home=home)
        self.assertEqual(result.returncode, 0, result.stderr)

    def native_bash(self) -> tuple[str, dict[str, str]]:
        environment = os.environ.copy()
        if os.name == "nt":
            git_bins = [
                Path(value) / "Git" / "bin"
                for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")
                if (value := os.environ.get(variable))
            ]
            git_bin = next((path for path in git_bins if (path / "bash.exe").is_file()), None)
            if git_bin is None:
                self.fail("Git Bash is required for the Windows shell-dispatch test")
            environment["PATH"] = str(git_bin) + os.pathsep + environment.get("PATH", "")
        bash = shutil.which("bash", path=environment.get("PATH"))
        if bash is None:
            self.fail("bash is required for the shell-dispatch test")
        return os.path.abspath(bash), environment

    def test_real_install_is_idempotent_and_uses_native_layout(self) -> None:
        root_rules = self.project / "RULES.md"
        root_rules.write_text("Root rules stay untouched.\n", encoding="utf-8")
        self.install()
        omp = self.project / ".omp"
        self.assertTrue((omp / "skills" / "taurus" / "SKILL.md").is_file())
        for skill in ("deliver", "verify", "panel", "ship", "style"):
            self.assertTrue((omp / "skills" / f"taurus-{skill}" / "SKILL.md").is_file())
        self.assertEqual(len(list((omp / "agents").glob("*.md"))), 10)
        self.assertTrue((omp / "extensions" / "taurus.ts").is_file())
        self.assertTrue((omp / "taurus" / "hooks" / "guard-git.py").is_file())
        self.assertTrue((omp / "taurus" / "agents" / "qa-verifier.md").is_file())
        self.assertTrue((omp / "taurus" / "commands" / "deliver.md").is_file())
        self.assertTrue((omp / "taurus" / "rules" / "always-on.md").is_file())
        self.assertFalse((omp / "taurus" / ".taurus-skill-source").exists())
        for untouched in ("config.yml", "models.yml", "auth.json"):
            self.assertFalse((omp / untouched).exists())
        rules = omp / "RULES.md"
        self.assertIn("taurus:begin", rules.read_text(encoding="utf-8"))
        self.assertIn("taurus:end", rules.read_text(encoding="utf-8"))
        self.assertEqual(root_rules.read_text(encoding="utf-8"), "Root rules stay untouched.\n")
        before = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.install()
        after = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_update_replaces_changed_assets_and_removes_unchanged_obsolete_assets(self) -> None:
        self.install()
        command = self.source / "commands" / "deliver.md"
        command.write_text(command.read_text(encoding="utf-8") + "\nUpdate fixture.\n", encoding="utf-8")
        obsolete = self.source / "commands" / "style.md"
        obsolete.unlink()
        self.install()
        self.assertIn("Update fixture.", (self.project / ".omp" / "taurus" / "commands" / "deliver.md").read_text(encoding="utf-8"))
        self.assertFalse((self.project / ".omp" / "taurus" / "commands" / "style.md").exists())

    def test_install_refuses_user_conflict_before_any_write(self) -> None:
        conflict = self.project / ".omp" / "skills" / "taurus" / "SKILL.md"
        conflict.parent.mkdir(parents=True)
        conflict.write_text("my skill\n", encoding="utf-8")
        rules = self.project / "RULES.md"
        rules.write_text("My project rules.\n", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("user asset", result.stderr)
        self.assertEqual(conflict.read_text(encoding="utf-8"), "my skill\n")
        self.assertEqual(rules.read_text(encoding="utf-8"), "My project rules.\n")
        self.assertFalse((self.project / ".omp" / "taurus-install.json").exists())
        self.assertFalse((self.project / ".omp" / "extensions" / "taurus.ts").exists())

    def test_update_refuses_modified_asset_before_creating_new_assets(self) -> None:
        self.install()
        managed = self.project / ".omp" / "taurus" / "commands" / "deliver.md"
        managed.write_text("user changes\n", encoding="utf-8")
        added = self.source / "commands" / "new-command.md"
        added.write_text("new source command\n", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("modified managed asset", result.stderr)
        self.assertEqual(managed.read_text(encoding="utf-8"), "user changes\n")
        self.assertFalse((self.project / ".omp" / "taurus" / "commands" / "new-command.md").exists())

    def test_update_refuses_modified_rules_block(self) -> None:
        self.install()
        rules = self.project / ".omp" / "RULES.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("Taurus", "User Taurus", 1), encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("modified managed rules", result.stderr)

    def test_uninstall_removes_only_unchanged_assets_and_preserves_project_content(self) -> None:
        rules = self.project / ".omp" / "RULES.md"
        rules.parent.mkdir()
        rules.write_text("Before rules.\n\nAfter rules placeholder.\n", encoding="utf-8")
        self.install()
        unmanaged = self.project / ".omp" / "keep.md"
        unmanaged.write_text("keep\n", encoding="utf-8")
        modified = self.project / ".omp" / "taurus" / "commands" / "deliver.md"
        modified.write_text("my command\n", encoding="utf-8")
        result = self.invoke("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(modified.is_file())
        self.assertEqual(modified.read_text(encoding="utf-8"), "my command\n")
        self.assertFalse((self.project / ".omp" / "skills" / "taurus").exists())
        self.assertFalse((self.project / ".omp" / "taurus" / "hooks" / "guard-git.py").exists())
        self.assertTrue(unmanaged.is_file())
        updated_rules = rules.read_text(encoding="utf-8")
        self.assertIn("Before rules.", updated_rules)
        self.assertIn("After rules placeholder.", updated_rules)
        self.assertNotIn("taurus:begin", updated_rules)
        self.assertFalse((self.project / ".omp" / "taurus-install.json").exists())

    def test_dry_run_writes_nothing(self) -> None:
        result = self.invoke("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would copy", result.stdout)
        self.assertEqual(list(self.project.iterdir()), [])
        self.install()
        before = {path.relative_to(self.project): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.project.rglob("*") if path.is_file()}
        result = self.invoke("--uninstall", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {path.relative_to(self.project): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in self.project.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_projects_are_isolated_and_installer_touches_no_home_configuration(self) -> None:
        other = self.work / "other-project"
        other.mkdir()
        home = self.work / "home"
        home.mkdir()
        self.install(home=home)
        self.assertFalse((other / ".omp").exists())
        self.assertEqual(list(home.iterdir()), [])
        self.install(other, home=home)
        self.assertTrue((other / ".omp" / "extensions" / "taurus.ts").is_file())
        self.assertTrue((self.project / ".omp" / "extensions" / "taurus.ts").is_file())

    def test_uninstall_rejects_malformed_markers_and_unsafe_manifest_paths(self) -> None:
        self.install()
        rules = self.project / ".omp" / "RULES.md"
        rules.write_text(rules.read_text(encoding="utf-8") + "<!-- taurus:begin - managed by taurus-skill OMP install, edits are overwritten -->\n", encoding="utf-8")
        result = self.invoke("--uninstall")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed Taurus markers", result.stderr)
        self.assertTrue((self.project / ".omp" / "taurus-install.json").exists())

        fresh = self.work / "unsafe-project"
        fresh.mkdir()
        outside = self.work / "outside.txt"
        outside.write_text("safe\n", encoding="utf-8")
        omp = fresh / ".omp"
        omp.mkdir()
        (omp / "taurus-install.json").write_text(json.dumps({
            "version": 1,
            "files": {"../outside.txt": "0" * 64},
            "rules_sha256": "0" * 64,
        }), encoding="utf-8")
        result = self.invoke("--uninstall", project=fresh)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe Taurus OMP manifest path", result.stderr)
        self.assertEqual(outside.read_text(encoding="utf-8"), "safe\n")

    def test_install_rejects_symlink_traversal(self) -> None:
        outside = self.work / "outside"
        outside.mkdir()
        (outside / "taurus-install.json").write_text("{not json", encoding="utf-8")
        try:
            (self.project / ".omp").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinks are unavailable: {exc}")
        result = self.invoke("--uninstall")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traversal", result.stderr)
        self.assertEqual([path.name for path in outside.iterdir()], ["taurus-install.json"])

    @unittest.skipUnless(os.name == "nt", "Windows junctions require Windows")
    def test_uninstall_rejects_windows_junction_traversal(self) -> None:
        outside = self.work / "junction-target"
        outside.mkdir()
        (outside / "taurus-install.json").write_text("{not json", encoding="utf-8")
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(self.project / ".omp"), str(outside)],
            check=False,
            text=True,
            capture_output=True,
        )
        if created.returncode != 0:
            self.skipTest(f"junctions are unavailable: {created.stderr}")
        result = self.invoke("--uninstall")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traversal", result.stderr)
        self.assertEqual([path.name for path in outside.iterdir()], ["taurus-install.json"])

    def test_uninstall_preserves_a_replaced_symlink_asset(self) -> None:
        self.install()
        managed = self.project / ".omp" / "taurus" / "commands" / "deliver.md"
        outside = self.work / "outside-command.md"
        outside.write_text("outside target\n", encoding="utf-8")
        managed.unlink()
        try:
            managed.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlinks are unavailable: {exc}")
        result = self.invoke("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(managed.is_symlink())
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside target\n")
        self.assertFalse((self.project / ".omp" / "extensions" / "taurus.ts").exists())


    def test_uninstall_preserves_a_modified_managed_rules_block(self) -> None:
        self.install()
        rules = self.project / ".omp" / "RULES.md"
        original = rules.read_text(encoding="utf-8")
        before_end, end_marker, after_end = original.rpartition("<!-- taurus:end -->")
        self.assertTrue(end_marker)
        modified = before_end + "\nUser managed-block edit.\n" + end_marker + after_end
        rules.write_text(modified, encoding="utf-8")
        result = self.invoke("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rules.read_text(encoding="utf-8"), modified)

    def test_generated_source_files_are_not_installed(self) -> None:
        self.install()
        cache = self.source / "hooks" / "__pycache__"
        cache.mkdir()
        (cache / "guard-git.cpython-313.pyc").write_bytes(b"cache")
        (self.source / "commands" / "generated.txt").write_text("generated\n", encoding="utf-8")
        self.install()
        self.assertFalse((self.project / ".omp" / "taurus" / "hooks" / "__pycache__").exists())
        self.assertFalse((self.project / ".omp" / "taurus" / "commands" / "generated.txt").exists())

    def test_relative_project_path_is_normalized_after_validation(self) -> None:
        relative = self.work / "relative-project"
        relative.mkdir()
        result = subprocess.run(
            [sys.executable, str(self.installer), "--project", "relative-project"],
            cwd=self.work,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((relative / ".omp" / "taurus-install.json").is_file())

    @unittest.skipUnless(os.name != "nt", "ancestor-link resolution is covered on POSIX")
    def test_project_identity_resolves_symlink_ancestor_before_dotdot(self) -> None:
        physical = self.work / "physical"
        nested = physical / "nested"
        actual = physical / "project"
        nested.mkdir(parents=True)
        actual.mkdir()
        alias = self.work / "ancestor-link"
        alias.symlink_to(nested, target_is_directory=True)
        requested = alias / ".." / "project"
        result = self.invoke(project=requested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((actual / ".omp" / "taurus-install.json").is_file())
        self.assertFalse((self.project / ".omp").exists())
        result = self.invoke("--uninstall", project=requested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((actual / ".omp" / "taurus-install.json").exists())
        self.assertFalse((self.project / ".omp").exists())


    def test_shell_target_dispatches_to_project_installer(self) -> None:
        home = self.work / "shell-home"
        home.mkdir()
        bash, environment = self.native_bash()
        environment["HOME"] = str(home)
        result = subprocess.run(
            [bash, str(self.source / "install.sh"), "--target", "omp", "--project", str(self.project)],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / ".omp" / "taurus-install.json").is_file())
        self.assertEqual(list(home.iterdir()), [])
        missing = subprocess.run(
            [bash, str(self.source / "install.sh"), "--target", "omp"],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )
        self.assertEqual(missing.returncode, 2)
        self.assertIn("requires --project", missing.stderr)
        rejected = subprocess.run(
            [bash, str(self.source / "install.sh"), "--target", "omp", "--project", str(self.project), "--githooks"],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("not supported", rejected.stderr)
        wrong_target = subprocess.run(
            [bash, str(self.source / "install.sh"), "--project", str(self.project), "--dry-run"],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )
        self.assertEqual(wrong_target.returncode, 2)
        self.assertIn("only supported with --target omp", wrong_target.stderr)


    def test_project_directory_must_already_exist(self) -> None:
        missing = self.work / "missing-project"
        result = self.invoke(project=missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must already exist", result.stderr)
        self.assertFalse(missing.exists())

if __name__ == "__main__":
    unittest.main()
