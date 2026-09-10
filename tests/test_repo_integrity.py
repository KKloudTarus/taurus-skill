#!/usr/bin/env python3
"""Structural checks on the skill pack itself. Run: python3 tests/test_repo_integrity.py"""

import glob
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "hooks", "lint-prose.py")

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    match = FRONTMATTER.match(text)
    if not match:
        return None, text
    fields, key = {}, None
    for line in match.group(1).splitlines():
        if re.match(r"^\s+", line) and key:
            fields[key] += " " + line.strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            fields[key] = value.strip()
    return fields, text[match.end():]


def skills():
    return sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")))


def references():
    return sorted(glob.glob(os.path.join(ROOT, "skills", "*", "references", "*.md")))


def agents():
    return sorted(glob.glob(os.path.join(ROOT, "agents", "*.md")))


def commands():
    return sorted(glob.glob(os.path.join(ROOT, "commands", "*.md")))


class TestSkills(unittest.TestCase):
    def test_the_pack_ships_exactly_one_skill(self):
        """One picker entry. The depth lives in references/, invisible to the picker."""
        self.assertEqual(len(skills()), 1, [os.path.dirname(p) for p in skills()])

    def test_references_carry_the_depth(self):
        expected = {
            "algorithm-rigor.md",
            "checklists.md",
            "clean-architecture.md",
            "conventional-commits.md",
            "engineering-baseline.md",
            "frontend-quality.md",
            "genai-agent-systems.md",
            "git-discipline.md",
            "infrastructure-delivery.md",
            "ml-engineering.md",
            "review-panel.md",
            "rewrites.md",
            "sre-operations.md",
            "system-design.md",
            "test-discipline.md",
            "verification-gate.md",
            "writing-voice.md",
        }
        found = {os.path.basename(path) for path in references()}
        self.assertEqual(found, expected)

    def test_every_skill_dir_has_a_skill_md(self):
        for d in sorted(glob.glob(os.path.join(ROOT, "skills", "*"))):
            if os.path.isdir(d):
                self.assertTrue(os.path.isfile(os.path.join(d, "SKILL.md")), d)

    def test_frontmatter_name_matches_directory(self):
        for path in skills():
            fields, _ = frontmatter(path)
            self.assertIsNotNone(fields, f"{path} has no frontmatter")
            self.assertEqual(fields.get("name"), os.path.basename(os.path.dirname(path)), path)

    def test_description_is_present_and_bounded(self):
        for path in skills():
            fields, _ = frontmatter(path)
            desc = fields.get("description", "")
            self.assertGreater(len(desc), 40, f"{path}: description too short to route on")
            self.assertLess(len(desc), 1024, f"{path}: description too long")

    def test_description_says_when_to_load(self):
        for path in skills():
            fields, _ = frontmatter(path)
            desc = fields.get("description", "").lower()
            self.assertTrue(
                any(w in desc for w in ("load", "use ", "when", "before")),
                f"{path}: description must say when to load it",
            )

    def test_body_is_substantial(self):
        for path in skills() + references():
            _, body = frontmatter(path)
            self.assertGreater(len(body.split()), 250, f"{path}: body too thin")

    def test_always_loaded_context_stays_small(self):
        path = os.path.join(ROOT, "rules", "always-on.md")
        with open(path, encoding="utf-8") as fh:
            words = fh.read().split()
        self.assertLessEqual(
            len(words), 350,
            f"always-on.md has {len(words)} words; move conditional detail into the skill",
        )

    def test_skill_router_stays_small(self):
        for path in skills():
            with open(path, encoding="utf-8") as fh:
                words = fh.read().split()
            self.assertLessEqual(
                len(words), 700,
                f"{path} has {len(words)} words; move conditional detail into references",
            )

    def test_cross_references_resolve(self):
        names = {os.path.basename(os.path.dirname(p)) for p in skills()}
        for path in skills() + commands() + references():
            _, body = frontmatter(path)
            for ref in re.findall(r"`([a-z][a-z-]+)` skill", body):
                self.assertIn(ref, names, f"{path} references unknown skill {ref}")

    def test_reference_links_resolve(self):
        known = {os.path.basename(p) for p in references()}
        for path in skills() + commands() + references():
            _, body = frontmatter(path)
            for ref in re.findall(r"`references/([a-z][a-z0-9-]*\.md)`", body):
                self.assertIn(ref, known, f"{path} points at a missing reference {ref}")

    def test_the_skill_routes_to_every_reference(self):
        """No orphan reference: if the router does not name it, it never gets read."""
        _, body = frontmatter(skills()[0])
        named = set(re.findall(r"`references/([a-z][a-z0-9-]*\.md)`", body))
        for path in references():
            self.assertIn(os.path.basename(path), named,
                          f"{os.path.basename(path)} is not routed to from SKILL.md")

    def test_no_stale_skill_name_references(self):
        """After consolidation, nothing may refer to the old sibling skills."""
        old_names = ("engineering-baseline", "writing-voice", "git-discipline",
                     "clean-architecture", "test-discipline", "algorithm-rigor",
                     "system-design", "verification-gate", "review-panel")
        pattern = re.compile(r"`(" + "|".join(old_names) + r")`(?!\.md)")
        for path in skills() + commands() + references() + [os.path.join(ROOT, "rules", "always-on.md")]:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            hit = pattern.search(body)
            self.assertIsNone(hit, f"{path} still refers to `{hit.group(1)}` as a skill" if hit else "")

    def test_references_say_when_to_load(self):
        for path in references():
            with open(path, encoding="utf-8") as fh:
                head = fh.readline().rstrip("\n")
            self.assertTrue(head.startswith("> Load when:"), f"{path}: missing the load hint")
            self.assertGreater(len(head), 60, f"{path}: load hint too thin to route on")


class TestAgents(unittest.TestCase):
    def test_agents_exist(self):
        expected = {
            "ai-ml-verifier",
            "algorithm-verifier",
            "architecture-critic",
            "decision-analyst",
            "frontend-quality-auditor",
            "performance-auditor",
            "platform-auditor",
            "qa-verifier",
            "reliability-auditor",
            "security-auditor",
        }
        found = {os.path.basename(path)[:-3] for path in agents()}
        self.assertEqual(found, expected)

    def test_frontmatter_name_matches_filename(self):
        for path in agents():
            fields, _ = frontmatter(path)
            self.assertIsNotNone(fields, f"{path} has no frontmatter")
            self.assertEqual(fields.get("name"), os.path.basename(path)[:-3], path)

    def test_agents_declare_tools_and_description(self):
        for path in agents():
            fields, _ = frontmatter(path)
            self.assertIn("tools", fields, path)
            self.assertGreater(len(fields.get("description", "")), 40, path)

    def test_review_agents_cannot_edit_code(self):
        for path in agents():
            fields, _ = frontmatter(path)
            tools = fields["tools"]
            for forbidden in ("Edit", "Write", "NotebookEdit"):
                self.assertNotIn(forbidden, tools, f"{path} must not be able to modify code")

    def test_agents_state_an_output_contract(self):
        for path in agents():
            _, body = frontmatter(path)
            self.assertIn("VERDICT", body, f"{path}: no structured output contract")


class TestCommands(unittest.TestCase):
    def test_commands_exist(self):
        self.assertGreaterEqual(len(commands()), 4)

    def test_commands_have_a_description(self):
        for path in commands():
            fields, _ = frontmatter(path)
            self.assertIsNotNone(fields, f"{path} has no frontmatter")
            self.assertGreater(len(fields.get("description", "")), 20, path)

    def test_commands_reference_only_existing_agents(self):
        known = {os.path.basename(p)[:-3] for p in agents()}
        for path in commands() + skills():
            _, body = frontmatter(path)
            for ref in re.findall(r"`([a-z][a-z-]+)` agent", body):
                self.assertIn(ref, known, f"{path} references unknown agent {ref}")


class TestExecutables(unittest.TestCase):
    def test_scripts_are_executable(self):
        for rel in ("install.sh", "hooks/guard-git.py", "hooks/lint-prose.py",
                    "hooks/lint-commit.py", "hooks/gate-report.py", "githooks/commit-msg",
                    "githooks/pre-commit", "githooks/pre-push"):
            path = os.path.join(ROOT, rel)
            self.assertTrue(os.access(path, os.X_OK), f"{rel} is not executable")

    def test_installer_shell_syntax(self):
        proc = subprocess.run(["bash", "-n", os.path.join(ROOT, "install.sh")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_source_marker_present(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, ".taurus-skill-source")))

    def test_own_claude_md_is_not_ignored(self):
        """The global gitignore hides CLAUDE.md everywhere; this repo un-ignores its own."""
        proc = subprocess.run(
            ["git", "-C", ROOT, "status", "--porcelain", "--ignored", "--untracked-files=all"],
            capture_output=True, text=True,
        )
        ignored = {line[3:] for line in proc.stdout.splitlines() if line.startswith("!!")}
        self.assertNotIn("CLAUDE.md", ignored, "CLAUDE.md is ignored in the source repo")

    def test_rules_file_present(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "rules", "always-on.md")))

    def test_the_installer_wires_the_git_hooks(self):
        """The hooks are the control of record, so the installer must set them up."""
        with open(os.path.join(ROOT, "install.sh"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("core.hooksPath", source)
        self.assertIn("--no-githooks", source, "no way to skip the global git config")

    def test_the_guard_runs_the_commit_linter(self):
        with open(os.path.join(ROOT, "hooks", "guard-git.py"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("lint-commit.py", source, "the guard does not run the commit linter")


COMMIT_LINT = os.path.join(ROOT, "hooks", "lint-commit.py")


def lint_message(text, label):
    return subprocess.run(
        [sys.executable, COMMIT_LINT, "--stdin", "--label", label],
        input=text, capture_output=True, text=True, timeout=30,
    )


class TestOwnHistory(unittest.TestCase):
    def test_every_commit_follows_conventional_commits(self):
        """The pack's own history is the first thing a reader checks."""
        proc = subprocess.run(
            ["git", "-C", ROOT, "log", "--no-merges", "-n", "50", "--format=%H%n%B%x00"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            self.skipTest("no git history available")
        for record in proc.stdout.split("\0"):
            record = record.strip("\n")
            if not record.strip():
                continue
            sha, _, body = record.partition("\n")
            out = lint_message(body.strip("\n"), sha[:8])
            self.assertEqual(out.returncode, 0, out.stdout)


class TestDocumentedExamples(unittest.TestCase):
    """Every example the pack prints must pass the validator that documents it."""

    def examples(self):
        found = []
        for rel in ("skills/taurus/references/conventional-commits.md",
                    "skills/taurus/references/git-discipline.md"):
            path = os.path.join(ROOT, rel)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL):
                first = block.split("\n", 1)[0]
                if re.match(r"^[a-z]+(\([a-z0-9._/-]+\))?!?: \S", first):
                    found.append((rel, block.rstrip("\n")))
        return found

    def test_examples_exist(self):
        self.assertGreaterEqual(len(self.examples()), 5)

    def test_every_commit_example_passes(self):
        header = re.compile(r"^[a-z]+(\([a-z0-9._/-]+\))?!?: \S")
        for rel, block in self.examples():
            # Blocks that show a rejected form label it on the same line.
            if "rejected" in block or "useless" in block:
                continue
            lines = [l for l in block.split("\n") if l.strip()]
            # A block of nothing but subjects is a list of examples, not one message.
            messages = lines if all(header.match(l) for l in lines) else [block]
            for message in messages:
                out = lint_message(message, rel)
                self.assertEqual(out.returncode, 0,
                                 f"{rel} documents an example the validator rejects:\n"
                                 f"{message}\n{out.stdout}")


def markdown_files():
    targets = []
    for pattern in ("*.md", "skills/*/SKILL.md", "skills/*/references/*.md",
                    "agents/*.md", "commands/*.md", "rules/*.md"):
        targets.extend(glob.glob(os.path.join(ROOT, pattern)))
    return sorted(targets)


class TestMarkdownStructure(unittest.TestCase):
    def test_code_fences_are_balanced(self):
        """An unclosed fence swallows the rest of the document."""
        for path in markdown_files():
            with open(path, encoding="utf-8") as fh:
                fences = [l for l in fh if l.startswith("```")]
            self.assertEqual(len(fences) % 2, 0,
                             f"{os.path.relpath(path, ROOT)}: {len(fences)} fence markers")

    def test_no_double_blank_lines(self):
        """Two blank lines in a row is what a stripped code fence leaves behind."""
        for path in markdown_files():
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            hit = re.search(r"\n[ \t]*\n[ \t]*\n", text)
            if hit:
                line = text[:hit.start()].count("\n") + 2
                self.fail(f"{os.path.relpath(path, ROOT)}:{line}: two blank lines in a row")

    def test_shell_examples_live_in_a_fence(self):
        """A command outside a fence gets linted as prose and renders as a paragraph."""
        starters = ("python3 ", "git ", "npm ", "go test", "chmod ", "cat > ", "grep ")
        for path in markdown_files():
            with open(path, encoding="utf-8") as fh:
                inside = False
                for n, line in enumerate(fh, 1):
                    if line.startswith("```"):
                        inside = not inside
                        continue
                    if not inside and line.startswith(starters):
                        self.fail(f"{os.path.relpath(path, ROOT)}:{n}: unfenced command "
                                  f"{line.strip()[:50]!r}")


class TestOwnProseIsClean(unittest.TestCase):
    def test_all_markdown_passes_the_linter(self):
        targets = markdown_files()
        self.assertGreater(len(targets), 10)
        proc = subprocess.run(
            [sys.executable, LINT, *targets], capture_output=True, text=True, timeout=120
        )
        self.assertEqual(proc.returncode, 0, "the pack violates its own writing standard:\n" + proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
