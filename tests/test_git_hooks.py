#!/usr/bin/env python3
"""Tests for githooks/. Run: python3 tests/test_git_hooks.py

These hooks are the control of record. They run inside git, after it has assembled
the message and staged the tree, so no option spelling, alias, shell expansion, or
heredoc can route around them. Every case here is a spelling that reached real git
past the PreToolUse guard at some point during development.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "githooks")
ATTRIBUTION = "Co-Authored-By: Claude <noreply@anthropic.com>"
ENV = dict(os.environ, TAURUS_ROOT=ROOT)


def git(repo, *args, env=ENV, check=False):
    proc = subprocess.run(["git", "-C", repo, *args],
                          capture_output=True, text=True, env=env, timeout=60)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc


class HookTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="hooks-test-")
        git(self.repo, "init", "-q", "-b", "main", check=True)
        git(self.repo, "config", "user.email", "dev@example.com", check=True)
        git(self.repo, "config", "user.name", "Dev", check=True)
        git(self.repo, "config", "core.excludesFile", "/dev/null", check=True)
        git(self.repo, "config", "core.hooksPath", HOOKS, check=True)
        self.write("a.txt", "a\n")
        git(self.repo, "add", "a.txt", check=True)
        self.commit("chore: init", check=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        if getattr(self, "bare", None):
            shutil.rmtree(self.bare, ignore_errors=True)

    def write(self, relpath, content):
        full = os.path.join(self.repo, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(relpath) else None
        with open(full, "w") as fh:
            fh.write(content)
        return full

    def commit(self, message, *extra, check=False):
        """Commit through the hooks."""
        return git(self.repo, "commit", "-q", *extra, "-m", message, check=check)

    def force_commit(self, message, *extra):
        """Commit past the hooks, to build the state a later hook must reject."""
        return git(self.repo, "commit", "-q", "--no-verify", *extra, "-m", message)

    def add_remote(self):
        self.bare = tempfile.mkdtemp(prefix="hooks-bare-")
        subprocess.run(["git", "init", "-q", "--bare", self.bare],
                       capture_output=True, check=True)
        git(self.repo, "remote", "add", "origin", self.bare, check=True)

    def assertRejected(self, proc, needle=None):
        self.assertNotEqual(proc.returncode, 0, f"expected rejection, got: {proc.stdout}")
        if needle:
            self.assertIn(needle, proc.stderr)

    def assertAccepted(self, proc):
        self.assertEqual(proc.returncode, 0, f"expected acceptance, got: {proc.stderr}")


class TestCommitMsgHook(HookTestCase):
    def test_rejects_a_non_conventional_subject(self):
        self.assertRejected(self.commit("wip", "--allow-empty"), "Conventional Commits")

    def test_rejects_attribution(self):
        self.assertRejected(self.commit("feat: x\n\n" + ATTRIBUTION, "--allow-empty"))

    def test_rejects_a_bundled_short_cluster(self):
        """`-am` reached real git past the PreToolUse guard for two rounds."""
        self.write("b.txt", "b\n")
        self.assertRejected(git(self.repo, "commit", "-q", "-am", "added stuff"))

    def test_accepts_an_em_dash(self):
        self.assertAccepted(self.commit("fix: raise pool — p99 was 1.8s", "--allow-empty"))

    def test_rejects_a_message_built_by_expansion(self):
        """The spelling the guard cannot read is exactly what this layer is for."""
        script = f'cd {self.repo} && git commit -q --allow-empty -m "$(printf wip)"'
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=ENV)
        self.assertRejected(proc)

    def test_accepts_a_conforming_message(self):
        self.assertAccepted(self.commit("feat(cache): add a write-through path",
                                        "--allow-empty"))

    def test_accepts_a_full_message_with_footers(self):
        body = ("feat(inventory)!: hold seats under a row-level lock\n\n"
                "Redis held the seat state.\n\n"
                "BREAKING CHANGE: HoldSeats no longer accepts a Redis client.\n\n"
                "Refs: PLAT-812")
        self.assertAccepted(self.commit(body, "--allow-empty"))


class TestPreCommitHook(HookTestCase):
    def test_rejects_staged_claude_md(self):
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md", check=True)
        self.assertRejected(self.commit("chore: notes"), "local agent config")

    def test_rejects_staged_claude_dir(self):
        self.write(".claude/settings.json", "{}\n")
        git(self.repo, "add", "-f", ".claude/settings.json", check=True)
        self.assertRejected(self.commit("chore: notes"), "local agent config")

    def test_rejects_staged_mcp_json(self):
        self.write(".mcp.json", "{}\n")
        git(self.repo, "add", "-f", ".mcp.json", check=True)
        self.assertRejected(self.commit("chore: notes"))

    def test_accepts_a_clean_tree(self):
        self.write("src.py", "x = 1\n")
        git(self.repo, "add", "src.py", check=True)
        self.assertAccepted(self.commit("feat(src): add x"))

    def test_source_repo_may_commit_its_own_config(self):
        self.write(".taurus-skill-source", "")
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md", ".taurus-skill-source", check=True)
        self.assertAccepted(self.commit("docs: add guidance"))


class TestPrePushHook(HookTestCase):
    def test_rejects_a_push_whose_history_carries_private_paths(self):
        """`git rm --cached` clears the tip and leaves the blob in history."""
        self.add_remote()
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md", check=True)
        self.force_commit("chore: notes")
        git(self.repo, "rm", "-q", "--cached", "CLAUDE.md", check=True)
        self.force_commit("chore: stop tracking it")
        self.assertNotIn("CLAUDE.md", git(self.repo, "ls-files").stdout)
        self.assertRejected(git(self.repo, "push", "-q", "origin", "main"),
                            "local agent config")

    def test_rejects_a_push_of_a_side_branch(self):
        self.add_remote()
        git(self.repo, "checkout", "-q", "-b", "leak", check=True)
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md", check=True)
        self.force_commit("chore: notes")
        git(self.repo, "checkout", "-q", "main", check=True)
        self.assertRejected(git(self.repo, "push", "-q", "origin", "leak:main"))

    def test_accepts_a_clean_push(self):
        self.add_remote()
        self.write("src.py", "x = 1\n")
        git(self.repo, "add", "src.py", check=True)
        self.commit("feat(src): add x", check=True)
        self.assertAccepted(git(self.repo, "push", "-q", "origin", "main"))


class TestChaining(HookTestCase):
    def test_a_repo_hook_still_runs(self):
        """core.hooksPath replaces .git/hooks, so the pack must chain to it."""
        local = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(local, exist_ok=True)
        marker = os.path.join(self.repo, "ran-local-hook")
        path = os.path.join(local, "commit-msg")
        with open(path, "w") as fh:
            fh.write(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
        os.chmod(path, 0o755)
        self.assertAccepted(self.commit("feat(cache): add a path", "--allow-empty"))
        self.assertTrue(os.path.exists(marker), "the repo's own commit-msg hook did not run")

    def test_a_repo_hook_can_still_reject(self):
        local = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(local, exist_ok=True)
        path = os.path.join(local, "commit-msg")
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\necho 'local rule says no' >&2\nexit 1\n")
        os.chmod(path, 0o755)
        self.assertRejected(self.commit("feat(cache): add a path", "--allow-empty"),
                            "local rule says no")

    def test_the_chained_pre_push_hook_receives_the_refs(self):
        """Draining stdin turns off every branch-protection hook on the machine."""
        self.add_remote()
        local = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(local, exist_ok=True)
        path = os.path.join(local, "pre-push")
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\nn=0\nwhile read -r a b c d; do n=$((n+1)); done\n"
                     'echo "REPO PRE-PUSH saw $n refs" >&2\n[ "$n" -gt 0 ] || exit 1\n')
        os.chmod(path, 0o755)
        self.write("src.py", "x = 1\n")
        git(self.repo, "add", "src.py", check=True)
        self.commit("feat(src): add x", check=True)
        proc = git(self.repo, "push", "-q", "origin", "main")
        self.assertIn("saw 1 refs", proc.stderr, proc.stderr)
        self.assertAccepted(proc)

    def test_hooks_the_pack_does_not_implement_still_run(self):
        """core.hooksPath replaces the directory, so every name needs a passthrough."""
        local = os.path.join(self.repo, ".git", "hooks")
        os.makedirs(local, exist_ok=True)
        log = os.path.join(self.repo, "hooklog")
        for name in ("prepare-commit-msg", "post-commit", "post-checkout", "post-merge"):
            path = os.path.join(local, name)
            with open(path, "w") as fh:
                fh.write(f'#!/bin/sh\necho "{name}" >> {log}\nexit 0\n')
            os.chmod(path, 0o755)
        self.assertAccepted(self.commit("feat(x): add a thing", "--allow-empty"))
        with open(log) as fh:
            ran = fh.read().split()
        self.assertIn("prepare-commit-msg", ran)
        self.assertIn("post-commit", ran)


class TestHookScripts(unittest.TestCase):
    ENFORCING = ("commit-msg", "pre-commit", "pre-push")
    PASSTHROUGH = ("applypatch-msg", "pre-applypatch", "post-applypatch",
                   "pre-merge-commit", "prepare-commit-msg", "post-commit",
                   "pre-rebase", "post-checkout", "post-merge", "post-rewrite",
                   "pre-auto-gc", "push-to-checkout", "sendemail-validate",
                   "reference-transaction", "post-index-change")

    def test_every_hook_exists_and_is_executable(self):
        for name in self.ENFORCING + self.PASSTHROUGH:
            path = os.path.join(HOOKS, name)
            self.assertTrue(os.path.isfile(path), f"{name} is missing")
            self.assertTrue(os.access(path, os.X_OK), f"{name} is not executable")

    def test_shell_syntax(self):
        for name in self.ENFORCING + self.PASSTHROUGH:
            proc = subprocess.run(["sh", "-n", os.path.join(HOOKS, name)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr}")

    def test_every_passthrough_chains_to_its_own_name(self):
        for name in self.PASSTHROUGH:
            with open(os.path.join(HOOKS, name), encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn(f"hooks/{name}", body, f"{name} chains to the wrong hook")

    def test_hooks_survive_a_missing_pack(self):
        """A stale core.hooksPath must not wedge every commit on the machine."""
        repo = tempfile.mkdtemp(prefix="hooks-missing-")
        try:
            env = dict(os.environ, TAURUS_ROOT="/nonexistent-taurus")
            git(repo, "init", "-q", "-b", "main", env=env)
            git(repo, "config", "user.email", "d@e.com", env=env)
            git(repo, "config", "user.name", "D", env=env)
            git(repo, "config", "core.hooksPath", HOOKS, env=env)
            proc = git(repo, "commit", "-q", "--allow-empty", "-m", "anything at all",
                       env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
