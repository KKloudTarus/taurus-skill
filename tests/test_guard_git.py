#!/usr/bin/env python3
"""Tests for hooks/guard-git.py. Run: python3 tests/test_guard_git.py"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "guard-git.py")

ALLOW, BLOCK = 0, 2


def run_guard(command, cwd, tool="Bash"):
    payload = json.dumps({
        "tool_name": tool,
        "tool_input": {"command": command},
        "cwd": cwd,
    })
    proc = subprocess.run(
        [sys.executable, GUARD], input=payload, capture_output=True, text=True, timeout=30
    )
    return proc.returncode, proc.stderr


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True)


class GuardTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="guard-test-")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "dev@example.com")
        git(self.repo, "config", "user.name", "Dev")
        # Isolate from the machine's global git config, which install.sh populates:
        # the ignore file, and core.hooksPath pointing at the pack's own git hooks.
        git(self.repo, "config", "core.excludesFile", "/dev/null")
        self.nohooks = tempfile.mkdtemp(prefix="guard-nohooks-")
        git(self.repo, "config", "core.hooksPath", self.nohooks)
        self.write("README.md", "hello\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-qm", "init")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(getattr(self, "nohooks", ""), ignore_errors=True)

    def write(self, relpath, content):
        full = os.path.join(self.repo, relpath)
        if os.path.dirname(relpath):
            os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(content)
        return full

    def assertBlocked(self, command, needle=None):
        code, err = run_guard(command, self.repo)
        self.assertEqual(code, BLOCK, f"expected block for {command!r}, stderr={err!r}")
        if needle:
            self.assertIn(needle, err)

    def assertAllowed(self, command):
        code, err = run_guard(command, self.repo)
        self.assertEqual(code, ALLOW, f"expected allow for {command!r}, stderr={err!r}")


class TestAttribution(GuardTestCase):
    def test_blocks_co_authored_by_claude(self):
        self.assertBlocked(
            'git commit -m "feat: add cache\n\nCo-Authored-By: Claude <noreply@anthropic.com>"',
            "AI attribution",
        )

    def test_blocks_generated_with_claude_code(self):
        self.assertBlocked('git commit -m "fix: retry\n\nGenerated with Claude Code"')

    def test_blocks_robot_emoji(self):
        self.assertBlocked('git commit -m "chore: bump \U0001F916"')

    def test_blocks_anthropic_mention(self):
        self.assertBlocked('git commit -m "docs: link anthropic guide"')

    def test_blocks_trailer_flag(self):
        self.assertBlocked('git commit -m "feat: x" --trailer "Co-Authored-By: Claude <a@anthropic.com>"')

    def test_blocks_claude_url(self):
        self.assertBlocked('git commit -m "feat: x\n\nhttps://claude.ai/code/session_1"')

    def test_allows_clean_message(self):
        self.assertAllowed('git commit -m "feat(cache): add write-through path"')

    def test_allows_message_mentioning_clause(self):
        self.assertAllowed('git commit -m "fix(sql): correct WHERE clause on tenant filter"')

    def test_attribution_checked_in_source_repo_too(self):
        open(os.path.join(self.repo, ".taurus-skill-source"), "w").close()
        self.assertBlocked('git commit -m "chore: x\n\nCo-Authored-By: Claude <a@anthropic.com>"')


class TestPrivatePaths(GuardTestCase):
    def test_blocks_explicit_add_of_claude_md(self):
        self.write("CLAUDE.md", "rules\n")
        self.assertBlocked("git add CLAUDE.md", "CLAUDE.md")

    def test_blocks_explicit_add_of_claude_dir(self):
        os.makedirs(os.path.join(self.repo, ".claude"), exist_ok=True)
        self.write(".claude/settings.json", "{}\n")
        self.assertBlocked("git add .claude/settings.json")

    def test_blocks_add_of_agents_md(self):
        self.write("AGENTS.md", "x\n")
        self.assertBlocked("git add AGENTS.md")

    def test_blocks_add_of_mcp_json(self):
        self.write(".mcp.json", "{}\n")
        self.assertBlocked("git add .mcp.json")

    def test_blocks_broad_add_when_private_file_untracked(self):
        self.write("CLAUDE.md", "rules\n")
        self.write("src.py", "x = 1\n")
        self.assertBlocked("git add .", "gitignore")

    def test_blocks_broad_add_when_only_a_global_gitignore_is_absent(self):
        """The guard is the backstop when the machine has no global ignore rules."""
        self.write(".claude/settings.json", "{}\n")
        self.assertBlocked("git add -A", ".claude")

    def test_allows_broad_add_when_private_file_is_ignored(self):
        self.write("CLAUDE.md", "rules\n")
        self.write(".gitignore", "CLAUDE.md\n.claude/\n")
        self.write("src.py", "x = 1\n")
        self.assertAllowed("git add .")

    def test_allows_broad_add_in_clean_repo(self):
        self.write("src.py", "x = 1\n")
        self.assertAllowed("git add -A")

    def test_blocks_commit_when_private_path_staged(self):
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md")
        self.assertBlocked('git commit -m "chore: notes"', "staged tree contains")

    def test_blocks_commit_dash_a_with_private_file(self):
        self.write("CLAUDE.md", "rules\n")
        self.assertBlocked('git commit -am "chore: notes"')

    def test_blocks_push_when_private_path_tracked(self):
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md")
        git(self.repo, "commit", "-qm", "chore: notes")
        self.assertBlocked("git push origin main", "git rm -r --cached")

    def test_allows_push_on_clean_repo(self):
        self.assertAllowed("git push origin main")

    def test_source_repo_may_commit_its_own_claude_dir(self):
        open(os.path.join(self.repo, ".taurus-skill-source"), "w").close()
        os.makedirs(os.path.join(self.repo, ".claude"), exist_ok=True)
        self.write(".claude/settings.json", "{}\n")
        self.assertAllowed("git add .claude/settings.json")


class TestCommandParsing(GuardTestCase):
    def test_detects_git_in_chained_command(self):
        self.write("CLAUDE.md", "rules\n")
        self.assertBlocked("make build && git add CLAUDE.md")

    def test_detects_git_after_env_prefix(self):
        self.assertBlocked('GIT_EDITOR=true git commit -m "x\n\nCo-Authored-By: Claude <a@anthropic.com>"')

    def test_detects_git_with_dash_c_flag(self):
        self.assertBlocked('git -C . commit -m "x by Claude Code"')

    def test_ignores_non_bash_tools(self):
        code, _ = run_guard("git add CLAUDE.md", self.repo, tool="Read")
        self.assertEqual(code, ALLOW)

    def test_ignores_unrelated_command(self):
        self.assertAllowed("ls -la && cat CLAUDE.md")

    def test_ignores_git_log_and_status(self):
        self.assertAllowed("git status --porcelain")
        self.assertAllowed("git log --oneline -5")

    def test_survives_unparseable_quoting(self):
        code, _ = run_guard("git commit -m 'unbalanced", self.repo)
        self.assertIn(code, (ALLOW, BLOCK))

    def test_survives_outside_a_repo(self):
        outside = tempfile.mkdtemp(prefix="guard-nonrepo-")
        try:
            code, _ = run_guard("git status", outside)
            self.assertEqual(code, ALLOW)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_malformed_payload_does_not_block(self):
        proc = subprocess.run(
            [sys.executable, GUARD], input="not json", capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, ALLOW)


class TestProseInCommitMessages(GuardTestCase):
    def test_allows_em_dash_in_commit_message(self):
        self.assertAllowed('git commit -m "fix: raise pool size — p99 was 1.8s"')

    def test_allows_natural_contrast_in_commit_message(self):
        self.assertAllowed('git commit -m "fix: it is not a network fault, it is a pool timeout"')

    def test_nonconventional_meta_opener_still_blocks(self):
        self.assertBlocked('git commit -m "Tóm lại, sửa lại retry policy"')

    def test_allows_plain_commit_message(self):
        self.assertAllowed('git commit -m "fix(pool): raise max conns to 60 so p99 stays under 300ms"')

    def test_allows_vietnamese_plain_commit_message(self):
        self.assertAllowed('git commit -m "fix(pool): nâng max conns lên 60, p99 giữ dưới 300ms"')


class TestConventionalCommits(GuardTestCase):
    def test_blocks_message_without_a_type(self):
        self.assertBlocked('git commit -m "add the cache layer"', "Conventional Commits")

    def test_blocks_unknown_type(self):
        self.assertBlocked('git commit -m "feet: add the cache layer"', "type-unknown")

    def test_blocks_missing_space_after_colon(self):
        self.assertBlocked('git commit -m "feat:add cache"', "header-no-space")

    def test_blocks_lowercase_breaking_change_footer(self):
        self.assertBlocked(
            'git commit -m "feat: rework config\n\nbreaking change: extends key moved"',
            "breaking-change-case",
        )

    def test_blocks_body_without_a_blank_line(self):
        self.assertBlocked(
            'git commit -m "feat: rework config\nthe body starts here"',
            "blank-line-before-body",
        )

    def test_blocks_subject_over_the_length_limit(self):
        long = "refactor(inventory): rename every single seat hold helper across the package"
        self.assertBlocked(f'git commit -m "{long}"', "header-too-long")

    def test_allows_a_conforming_message(self):
        self.assertAllowed('git commit -m "feat(cache): add a write-through path"')

    def test_allows_a_breaking_change_footer(self):
        self.assertAllowed(
            'git commit -m "feat(api)!: drop the v1 header" '
            '-m "BREAKING CHANGE: clients must send Accept-Version"'
        )

    def test_separate_dash_m_flags_become_paragraphs(self):
        """git joins -m values with a blank line, so the second one is a body."""
        self.assertAllowed('git commit -m "fix(pool): reuse idle conns" -m "Closes #123"')

    def test_reads_the_message_from_a_file(self):
        self.write("msg.txt", "add the cache layer\n")
        self.assertBlocked("git commit -F msg.txt", "header-no-type")

    def test_allows_a_conforming_message_file(self):
        self.write("msg.txt", "feat(cache): add a write-through path\n")
        self.assertAllowed("git commit -F msg.txt")

    def test_blocks_a_message_file_that_does_not_exist_yet(self):
        """A file written by the same command line is invisible to a PreToolUse hook."""
        self.assertBlocked("git commit -F absent.txt", "does not exist yet")

    def test_blocks_a_message_piped_on_stdin(self):
        """`-F -` would otherwise skip every check the guard runs."""
        self.assertBlocked("git commit -F - ", "piped in")
        self.assertBlocked("git commit --file - ", "piped in")
        self.assertBlocked("git commit --file=-", "piped in")
        self.assertBlocked("git commit -F-", "piped in")

    def test_a_real_message_file_is_still_allowed(self):
        self.write("msg.txt", "docs: describe the hold state machine\n")
        self.assertAllowed("git commit --file msg.txt")

    def test_editor_flow_is_not_second_guessed(self):
        self.assertAllowed("git commit --amend --no-edit")

    def test_conventional_check_applies_in_the_source_repo(self):
        open(os.path.join(self.repo, ".taurus-skill-source"), "w").close()
        self.assertBlocked('git commit -m "add the cache layer"', "Conventional Commits")

    def test_tag_message_is_not_held_to_the_commit_grammar(self):
        self.assertAllowed('git tag -a v1.2.0 -m "Release 1.2.0"')


DOLLAR = "\x24"
BACKTICK = "\x60"
LT = "\x3c"
ATTRIB = "Co-Authored-By: Claude " + DOLLAR.replace(DOLLAR, "<noreply@anthropic.com>")


class TestParserDifferential(GuardTestCase):
    """git and bash parse a command line by rules shlex does not share.

    Every case here was observed reaching real git with the guard reporting success.
    """

    def setUp(self):
        super().setUp()
        self.msg = self.write("msg.txt", "chore: x\n\n" + ATTRIB + "\n")

    def test_bundled_short_option_cluster(self):
        self.assertBlocked('git commit -am "added the cache layer"', "Conventional Commits")

    def test_bundled_cluster_with_attribution(self):
        self.assertBlocked('git commit -am "chore: x\n\n' + ATTRIB + '"', "AI attribution")

    def test_sticky_short_value(self):
        self.assertBlocked("git commit -F" + self.msg, "AI attribution")

    def test_abbreviated_long_option(self):
        self.assertBlocked("git commit --fil=" + self.msg, "AI attribution")
        self.assertBlocked('git commit --mes="chore: x\n\n' + ATTRIB + '"', "AI attribution")

    def test_value_taking_global_flag_no_longer_shifts_the_subcommand(self):
        """`--attr-source HEAD` used to make the guard read "HEAD" as the subcommand."""
        self.assertBlocked("git --attr-source HEAD commit -m 'x by Claude Code'",
                           "AI attribution")

    def test_unknown_global_flag_fails_closed(self):
        self.assertBlocked("git --some-future-flag value commit -m 'chore: x'",
                           "cannot parse")

    def test_inline_alias_is_resolved(self):
        self.assertBlocked("git -c alias.ci=commit ci -m 'x by Claude Code'",
                           "AI attribution")

    def test_configured_alias_is_resolved(self):
        git(self.repo, "config", "alias.ci", "commit")
        self.assertBlocked("git ci -m 'x by Claude Code'", "AI attribution")

    def test_shell_alias_is_refused(self):
        git(self.repo, "config", "alias.ci", "!git commit")
        self.assertBlocked("git ci -m 'anything'", "shell alias")

    def test_message_reuse_from_an_existing_commit(self):
        self.write("b.txt", "b\n")
        git(self.repo, "add", "b.txt")
        git(self.repo, "commit", "-qm", "chore: tidy\n\n" + ATTRIB)
        self.assertBlocked("git commit -C HEAD", "AI attribution")
        self.assertBlocked("git commit --reuse-message=HEAD", "AI attribution")


class TestUnmodeledShell(GuardTestCase):
    def test_command_substitution_with_a_write_verb(self):
        self.assertBlocked('echo "' + DOLLAR + '(git add CLAUDE.md)"', "command substitution")

    def test_backtick_with_a_write_verb(self):
        self.assertBlocked('echo "' + BACKTICK + 'git push origin main' + BACKTICK + '"',
                           "command substitution")

    def test_ansi_c_quoting(self):
        self.assertBlocked("git commit -m 'chore: t' -m " + DOLLAR + "'Co-Authored-By: Claude'",
                           "ANSI-C")

    def test_process_substitution(self):
        self.assertBlocked("git commit -F " + LT + "(printf 'x')")

    def test_expansion_in_a_commit_argument(self):
        """The guard reads pre-expansion text, so it is not the message git gets."""
        self.assertBlocked('git commit -m "feat: x" -m "don\'t ' + DOLLAR
                           + '(cat attr.txt) won\'t"', "shell expansion")

    def test_single_quoted_expansion_is_literal(self):
        self.assertAllowed("git commit -m 'docs: explain " + DOLLAR + "(pwd) in the guide'")

    def test_sh_dash_c(self):
        self.assertBlocked('bash -c "git add CLAUDE.md"', "sh -c")

    def test_xargs(self):
        self.assertBlocked("xargs git add CLAUDE.md", "xargs")

    def test_read_only_command_substitution_is_allowed(self):
        """No write verb, so nothing is hidden that matters."""
        self.assertAllowed('echo "' + DOLLAR + '(git log --oneline)"')

    def test_read_only_sh_dash_c_is_allowed(self):
        self.assertAllowed('bash -c "git status"')

    def test_heredoc_body_is_data_not_a_command(self):
        """Writing docs that mention git must not read as running git."""
        self.assertAllowed(
            "python3 - <<'PY'\n"
            "text = 'run " + BACKTICK + "git commit -F <file>" + BACKTICK + " after writing it'\n"
            "open('README.md', 'w').write(text)\n"
            "PY"
        )

    def test_single_quoted_text_cannot_expand(self):
        """bash does not substitute inside single quotes, so neither does the guard."""
        self.assertAllowed("echo 'see " + DOLLAR + "(git add x) in the manual'")

    def test_double_quoted_substitution_still_blocks(self):
        self.assertBlocked('echo "' + DOLLAR + '(git add CLAUDE.md)"', "command substitution")


class TestWrappers(GuardTestCase):
    def setUp(self):
        super().setUp()
        self.write("CLAUDE.md", "rules\n")

    def test_timeout_wrapper(self):
        self.assertBlocked("timeout 30 git add CLAUDE.md", "CLAUDE.md")

    def test_nice_with_a_flag(self):
        self.assertBlocked("nice -n 5 git add CLAUDE.md", "CLAUDE.md")

    def test_sudo_with_a_flag(self):
        self.assertBlocked("sudo -u dev git add CLAUDE.md", "CLAUDE.md")

    def test_env_with_a_flag(self):
        self.assertBlocked("env -i git add CLAUDE.md", "CLAUDE.md")


class TestBroadAdd(GuardTestCase):
    def setUp(self):
        super().setUp()
        self.write("CLAUDE.md", "rules\n")
        self.write("src.py", "x = 1\n")

    def test_dot_slash(self):
        self.assertBlocked("git add ./", "CLAUDE.md")

    def test_glob(self):
        self.assertBlocked("git add *", "CLAUDE.md")

    def test_explicit_safe_path_is_allowed(self):
        self.assertAllowed("git add src.py")


class TestPushRefs(GuardTestCase):
    def test_blocks_pushing_a_branch_that_carries_private_paths(self):
        git(self.repo, "checkout", "-q", "-b", "leak")
        self.write("CLAUDE.md", "rules\n")
        git(self.repo, "add", "-f", "CLAUDE.md")
        git(self.repo, "commit", "-qm", "chore: notes")
        git(self.repo, "checkout", "-q", "main")
        self.assertBlocked("git push origin leak:main", "CLAUDE.md")

    def test_allows_pushing_a_clean_branch(self):
        self.assertAllowed("git push origin main")


class TestMessageFileSafety(GuardTestCase):
    def test_refuses_a_fifo(self):
        path = os.path.join(self.repo, "fifo")
        os.mkfifo(path)
        try:
            self.assertBlocked(f"git commit -F {path}", "not a regular file")
        finally:
            os.unlink(path)

    def test_refuses_proc(self):
        self.assertBlocked("git commit -F /proc/self/environ", "refusing to read")

    def test_refuses_dev(self):
        self.assertBlocked("git commit -F /dev/zero", "refusing to read")

    def test_refuses_an_oversized_file(self):
        self.write("big.txt", "feat(x): s\n\n" + ("body line\n" * 20000))
        self.assertBlocked("git commit -F big.txt", "over the")

    def test_does_not_echo_file_contents(self):
        self.write("creds.txt", "aws_secret_access_key = SENSITIVE_EXAMPLE_VALUE\n")
        code, err = run_guard("git commit -F creds.txt", self.repo)
        self.assertEqual(code, BLOCK)
        self.assertNotIn("SENSITIVE_EXAMPLE_VALUE", err)

    def test_reads_a_real_message_file(self):
        self.write("msg.txt", "feat(cache): add a write-through path\n")
        self.assertAllowed("git commit -F msg.txt")


class TestNoFalsePositives(GuardTestCase):
    def test_trailer_without_a_message_is_allowed(self):
        """git opens the editor for the subject; the guard never sees it."""
        self.assertAllowed("git commit --trailer 'Refs: #1'")

    def test_trailer_carrying_attribution_is_still_blocked(self):
        self.assertBlocked("git commit --trailer '" + ATTRIB + "'", "AI attribution")

    def test_no_verify_is_blocked(self):
        """It skips the commit-msg hook, which is where the standard is enforced."""
        self.assertBlocked('git commit --no-verify -m "fix(a): correct the window"',
                           "no-verify")
        self.assertBlocked('git commit -n -m "fix(a): correct the window"', "no-verify")

    def test_common_commit_flags(self):
        self.assertAllowed('git commit -s -m "fix(a): correct the window"')
        self.assertAllowed('git commit --amend -m "fix(a): correct the window"')
        self.assertAllowed('git commit --author "D <d@e.com>" -m "fix(a): correct it"')

    def test_read_commands_are_untouched(self):
        for cmd in ("git status --porcelain", "git log --oneline -5", "git diff --cached",
                    "git show HEAD", "git branch -a"):
            self.assertAllowed(cmd)


class TestOptionalValueOptions(GuardTestCase):
    """git gives -u and -S a value only when it is stuck to the option.

    Consuming the next token instead shifts the parse off the message entirely.
    """

    def test_dash_u_before_a_message(self):
        self.assertBlocked('git commit -u -m "feat: x\n\n' + ATTRIB + '"', "AI attribution")

    def test_long_untracked_files_before_a_message(self):
        self.assertBlocked('git commit --untracked-files -m "feat: x\n\n' + ATTRIB + '"',
                           "AI attribution")

    def test_dash_s_before_a_message(self):
        self.assertBlocked('git commit -S -m "feat: x\n\n' + ATTRIB + '"', "AI attribution")

    def test_stuck_value_is_still_consumed(self):
        self.assertAllowed('git commit -uall -m "fix(a): correct the window"')
        self.assertAllowed('git commit --untracked-files=all -m "fix(a): correct it"')


class TestPathspecMagic(GuardTestCase):
    def setUp(self):
        super().setUp()
        self.write("CLAUDE.md", "rules\n")

    def test_icase_magic(self):
        self.assertBlocked("git add ':(icase)claude.md'", "CLAUDE.md")

    def test_top_magic(self):
        self.assertBlocked("git add ':/CLAUDE.md'", "CLAUDE.md")

    def test_update_index(self):
        self.assertBlocked("git update-index --add CLAUDE.md", "CLAUDE.md")

    def test_pathspec_from_file(self):
        self.write("list.txt", "CLAUDE.md\n")
        self.assertBlocked("git add --pathspec-from-file=list.txt", "CLAUDE.md")


class TestUnreadableHeredoc(GuardTestCase):
    def test_unterminated_heredoc_blocks(self):
        self.assertBlocked("cat " + LT + LT + "EOF\nblah\ngit add CLAUDE.md",
                           "cannot be determined")

    def test_heredoc_with_an_unreadable_delimiter_blocks(self):
        self.assertBlocked("cat " + LT + LT + DOLLAR + "V\nblah\ngit add CLAUDE.md",
                           "cannot be determined")


class TestParameterExpansion(GuardTestCase):
    def test_a_message_from_a_variable_is_refused(self):
        self.assertBlocked('M="' + ATTRIB + '"\ngit commit -m "feat(x): y" -m "$M"',
                           "shell expansion")

    def test_a_pathspec_from_a_variable_is_treated_as_broad(self):
        self.write("CLAUDE.md", "rules\n")
        self.assertBlocked("FILES=CLAUDE.md\ngit add $FILES", "CLAUDE.md")
        self.assertBlocked("FILES=CLAUDE.md\ngit add ${FILES}", "CLAUDE.md")

    def test_a_single_quoted_dollar_is_literal(self):
        self.assertAllowed("git commit -m 'docs: explain " + DOLLAR + "HOME in the guide'")


class TestLinterFailure(GuardTestCase):
    def test_a_linter_exiting_with_an_unexpected_code_blocks(self):
        """A non-zero exit that is not 1 means the message was never checked."""
        import shutil as _shutil
        sandbox = tempfile.mkdtemp(prefix="guard-stub-")
        try:
            for name in ("lint-prose.py", "lint-commit.py"):
                with open(os.path.join(sandbox, name), "w") as fh:
                    fh.write("import sys\nsys.exit(3)\n")
            _shutil.copy(GUARD, os.path.join(sandbox, "guard-git.py"))
            _shutil.copy(os.path.join(ROOT, "hooks", "shellscan.py"), sandbox)
            payload = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "feat(a): add a thing"'},
                "cwd": self.repo,
            })
            proc = subprocess.run(
                [sys.executable, os.path.join(sandbox, "guard-git.py")],
                input=payload, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, BLOCK, proc.stderr)
            self.assertIn("exited 3", proc.stderr)
        finally:
            _shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
