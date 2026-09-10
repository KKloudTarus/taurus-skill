#!/usr/bin/env python3
"""Tests for hooks/lint-commit.py. Run: python3 tests/test_lint_commit.py"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "hooks", "lint-commit.py")


def run(message, *extra):
    proc = subprocess.run(
        [sys.executable, LINT, "--stdin", "--label", "msg", "--format", "json", *extra],
        input=message, capture_output=True, text=True, timeout=30,
    )
    findings = json.loads(proc.stdout) if proc.stdout.strip() else []
    return proc.returncode, {f["rule"] for f in findings}, findings


class LintTestCase(unittest.TestCase):
    def assertClean(self, message, *extra):
        code, rules, _ = run(message, *extra)
        self.assertEqual(code, 0, f"expected clean, got {sorted(rules)} for {message!r}")

    def assertRule(self, message, rule, *extra, severity="error"):
        """A rule that does not fail the run does not enforce anything.

        Checking only that the rule appears lets a downgrade to `warn` pass, and a
        warning exits 0, so the guard and the commit-msg hook both allow the commit.
        """
        code, rules, findings = run(message, *extra)
        self.assertIn(rule, rules, f"expected [{rule}], got {sorted(rules)} for {message!r}")
        hit = next(f for f in findings if f["rule"] == rule)
        self.assertEqual(hit["severity"], severity,
                         f"[{rule}] is {hit['severity']}, expected {severity}")
        if severity == "error":
            self.assertEqual(code, 1, f"[{rule}] did not fail the run for {message!r}")
        return findings


class TestValidMessages(LintTestCase):
    def test_type_and_description(self):
        self.assertClean("docs: correct spelling of CHANGELOG")

    def test_type_scope_description(self):
        self.assertClean("feat(lang): add Polish language")

    def test_breaking_bang(self):
        self.assertClean("feat!: send an email to the customer when a product is shipped")

    def test_breaking_scope_and_bang(self):
        self.assertClean("feat(api)!: send an email when a product is shipped")

    def test_breaking_change_footer(self):
        self.assertClean(
            "feat: allow provided config object to extend other configs\n\n"
            "BREAKING CHANGE: `extends` key is now used for extending other config files"
        )

    def test_hyphenated_breaking_token_is_synonymous(self):
        self.assertClean("feat: drop node 6 support\n\nBREAKING-CHANGE: uses newer JS features")

    def test_multi_paragraph_body_and_multiple_footers(self):
        self.assertClean(
            "fix: prevent racing of requests\n\n"
            "Introduce a request id and a reference to latest request. Dismiss\n"
            "incoming responses other than from latest request.\n\n"
            "Remove timeouts which were used to mitigate the racing issue.\n\n"
            "Reviewed-by: Z\nRefs: #123"
        )

    def test_space_hash_footer_separator(self):
        self.assertClean("fix(pool): reuse idle conns\n\nCloses #123")

    def test_footer_value_spans_newlines(self):
        self.assertClean(
            "feat: rework config loading\n\n"
            "BREAKING CHANGE: the extends key now points at another file,\n"
            "so every caller must update its config before upgrading"
        )

    def test_every_allowed_type(self):
        for t in ("feat", "fix", "build", "chore", "ci", "docs",
                  "perf", "refactor", "revert", "style", "test"):
            self.assertClean(f"{t}(core): change something small")

    def test_scope_may_carry_a_path(self):
        self.assertClean("refactor(internal/order): split the state machine")

    def test_body_sentence_with_a_colon_is_not_a_footer(self):
        self.assertClean(
            "fix(pool): raise max conns to 60\n\n"
            "Verified with a contention test: 1 winner, 199 rejected"
        )

    def test_acronym_may_start_the_description(self):
        self.assertClean("fix: API returns 409 on idempotency key reuse")


class TestHeaderStructure(LintTestCase):
    def test_missing_type_prefix(self):
        self.assertRule("add the cache layer", "header-no-type")

    def test_colon_without_space(self):
        self.assertRule("feat:add cache", "header-no-space")

    def test_type_prefix_without_description(self):
        self.assertRule("feat:", "header-no-description")

    def test_leading_whitespace(self):
        self.assertRule("  feat: add cache", "header-leading-space")

    def test_unknown_type(self):
        findings = self.assertRule("feet: add cache", "type-unknown")
        self.assertIn("feat", findings[0]["fix"])

    def test_uppercase_type(self):
        self.assertRule("Feat: add cache", "type-case")

    def test_description_may_not_end_with_a_period(self):
        self.assertRule("fix: correct the retry window.", "description-period")

    def test_header_over_72_characters(self):
        long = "refactor(inventory): rename every single seat hold helper across the package"
        self.assertGreater(len(long), 72)
        self.assertRule(long, "header-too-long")

    def test_header_at_72_characters_passes(self):
        header = "fix(inventory): " + "a" * (72 - len("fix(inventory): "))
        self.assertEqual(len(header), 72)
        self.assertClean(header)

    def test_capitalized_description_is_only_a_warning(self):
        code, rules, _ = run("fix: Correct the retry window")
        self.assertEqual(code, 0)
        self.assertIn("description-case", rules)

    def test_warning_fails_under_severity_warn(self):
        code, _, _ = run("fix: Correct the retry window", "--severity", "warn")
        self.assertEqual(code, 1)


class TestScope(LintTestCase):
    def test_empty_scope(self):
        self.assertRule("fix(): correct the window", "scope-empty")

    def test_scope_with_spaces(self):
        self.assertRule("fix(My Module): correct the window", "scope-format")

    def test_uppercase_scope(self):
        self.assertRule("fix(Inventory): correct the window", "scope-format")


class TestBodyAndFooters(LintTestCase):
    def test_body_must_follow_a_blank_line(self):
        self.assertRule("fix: correct retry\nthis is the body", "blank-line-before-body")

    def test_breaking_change_must_be_uppercase(self):
        self.assertRule("feat: x\n\nbreaking change: config moved", "breaking-change-case")

    def test_mixed_case_breaking_change_is_rejected(self):
        self.assertRule("feat: x\n\nBreaking Change: config moved", "breaking-change-case")

    def test_breaking_change_needs_a_description(self):
        self.assertRule("feat: x\n\nBREAKING CHANGE:", "breaking-change-empty")

    def test_breaking_change_outside_the_footer_section(self):
        self.assertRule(
            "feat: x\n\nBREAKING CHANGE: config moved\n\nplain body prose follows it",
            "breaking-change-not-a-footer",
        )

    def test_footer_section_may_span_several_blocks(self):
        """The spec ends a footer at the next token, and a blank line is a separator."""
        self.assertClean(
            "feat(inventory)!: hold seats under a row-level lock\n\n"
            "Redis held the seat state.\n\n"
            "BREAKING CHANGE: HoldSeats no longer accepts a Redis client.\n\n"
            "Refs: PLAT-812\nReviewed-by: Z"
        )

    def test_footer_token_must_use_hyphens(self):
        findings = self.assertRule(
            "fix: x\n\nReviewed by: Z\nRefs: #123", "footer-token-whitespace"
        )
        self.assertIn("Reviewed-by", findings[0]["fix"])

    def test_bang_without_a_footer_is_only_a_warning(self):
        code, rules, _ = run("feat(api)!: drop the v1 header")
        self.assertEqual(code, 0)
        self.assertIn("breaking-change-undocumented", rules)


class TestGeneratedMessages(LintTestCase):
    def test_merge_commit_is_skipped(self):
        self.assertClean("Merge branch 'main' into feat/seat-hold")

    def test_merge_pull_request_is_skipped(self):
        self.assertClean("Merge pull request #12 from taurus/feat-x")

    def test_git_generated_revert_is_skipped(self):
        self.assertClean('Revert "feat: add cache"\n\nThis reverts commit abc1234.')

    def test_fixup_is_skipped(self):
        self.assertClean("fixup! feat: add cache")

    def test_squash_is_skipped(self):
        self.assertClean("squash! feat: add cache")

    def test_empty_message_is_skipped(self):
        self.assertClean("")
        self.assertClean("\n\n")


class TestGitEditorArtifacts(LintTestCase):
    def test_comment_lines_are_ignored_for_an_editor_buffer(self):
        self.assertClean(
            "feat(cache): add write-through path\n"
            "# Please enter the commit message for your changes.\n"
            "# On branch main\n",
            "--strip-comments",
        )

    def test_comment_lines_are_kept_on_stdin(self):
        """git's cleanup for -m and -F is `whitespace`, which keeps # lines."""
        self.assertRule("# updated some stuff, no type here", "header-no-type")

    def test_leading_blank_lines_do_not_hide_the_subject(self):
        """git drops them and takes the next line as the subject."""
        self.assertRule(" \nadded the cache layer", "header-no-type")

    def test_verbose_diff_after_scissors_is_ignored(self):
        self.assertClean(
            "feat(cache): add write-through path\n\n"
            "# ------------------------ >8 ------------------------\n"
            "diff --git a/x b/x\n"
            "+not a footer: at all\n"
        )

    def test_crlf_line_endings(self):
        self.assertClean("feat(cache): add path\r\n\r\nBody line here.\r\n")


class TestPrTitleMode(LintTestCase):
    def test_squash_merge_number_suffix_is_stripped(self):
        self.assertClean("feat(gateway): add route policy registry (#412)", "--pr-title")

    def test_pr_title_still_needs_a_type(self):
        self.assertRule("add route policy registry (#412)", "header-no-type", "--pr-title")

    def test_pr_title_ignores_a_body(self):
        self.assertClean("feat(gateway): add registry\nnot a real body", "--pr-title")


class TestBreakingChangeSeparator(LintTestCase):
    def test_colon_without_a_space_is_rejected(self):
        self.assertRule("feat: x\n\nBREAKING CHANGE:no space", "breaking-change-separator")

    def test_space_before_the_colon_is_rejected(self):
        self.assertRule("feat: x\n\nBREAKING CHANGE : spaced", "breaking-change-separator")

    def test_hash_separator_is_rejected_as_a_separator_not_a_case_error(self):
        findings = self.assertRule("feat: x\n\nBREAKING CHANGE #123", "breaking-change-separator")
        self.assertNotIn("breaking-change-case", {f["rule"] for f in findings})


class TestBodyProseIsNotAFooter(LintTestCase):
    def test_two_word_phrase_with_a_colon_is_body_prose(self):
        self.assertClean("fix(pool): raise max conns to 60\n\nTest results: 1 winner, 199 rejected")

    def test_three_word_phrase_with_a_colon_is_body_prose(self):
        self.assertClean("fix(pool): raise max conns\n\nOne more thing: it works")

    def test_a_typo_next_to_a_real_footer_is_still_caught(self):
        self.assertRule("fix: x\n\nReviewed by: Z\nRefs: #123", "footer-token-whitespace")


class TestBoundaries(LintTestCase):
    def test_73_characters_fails(self):
        header = "fix(inventory): " + "a" * (73 - len("fix(inventory): "))
        self.assertEqual(len(header), 73)
        self.assertRule(header, "header-too-long")

    def test_pr_title_suffix_is_actually_stripped(self):
        """The title must be over the limit with the suffix and under it without."""
        title = "feat(inventory): hold every single seat under one row-level lock now (#412)"
        self.assertGreater(len(title), 72)
        self.assertLessEqual(len(title) - len(" (#412)"), 72)
        self.assertClean(title, "--pr-title")
        self.assertRule(title, "header-too-long")  # without --pr-title it fails

    def test_description_leading_space(self):
        self.assertRule("feat:  add cache", "description-leading-space")

    def test_cr_only_line_endings(self):
        self.assertRule("feat: add path\rbody line", "blank-line-before-body")

    def test_scissors_content_is_ignored(self):
        self.assertClean(
            "feat(cache): add write-through path\n\n"
            "body\n\n"
            "------------------------ >8 ------------------------\n"
            "breaking change: this would fail if it were read\n"
        )

    def test_pr_title_whitespace_run_is_not_quadratic(self):
        import time
        start = time.perf_counter()
        run("feat: x" + " " * 40000 + "#", "--pr-title")
        self.assertLess(time.perf_counter() - start, 2.0)


class TestOutputBounds(LintTestCase):
    def test_findings_are_capped(self):
        message = "feat: x\n\n" + "\n\n".join(f"breaking change: {n}" for n in range(200))
        proc = subprocess.run(
            [sys.executable, LINT, "--stdin", "--label", "msg"],
            input=message, capture_output=True, text=True,
        )
        self.assertIn("more findings", proc.stdout)
        self.assertLess(len(proc.stdout), 60000)

    def test_no_excerpt_omits_the_text(self):
        proc = subprocess.run(
            [sys.executable, LINT, "--stdin", "--label", "msg", "--no-excerpt"],
            input="aws_secret_access_key = SENSITIVE", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("SENSITIVE", proc.stdout)
        self.assertIn("header-no-type", proc.stdout)


class TestEncoding(LintTestCase):
    def test_non_utf8_file_does_not_crash(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as fh:
            fh.write(b"feat: caf\xe9 subject\n")
            path = fh.name
        try:
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
        finally:
            os.unlink(path)


class TestCommentHandling(LintTestCase):
    def test_a_hash_subject_is_not_dropped(self):
        """git's cleanup for -m and -F keeps # lines, so the subject is real."""
        self.assertRule("#nope not conventional at all", "header-no-type")

    def test_a_hash_subject_is_not_dropped_from_a_file_either(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("# TODO rewrite this\nfix(a): x\n")
            path = fh.name
        try:
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("header-no-type", proc.stdout)
        finally:
            os.unlink(path)

    def test_an_editor_comment_block_is_dropped(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("feat(cache): add a path\n"
                     "# Please enter the commit message for your changes.\n"
                     "# On branch main\n")
            path = fh.name
        try:
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)
        finally:
            os.unlink(path)

    def test_strip_comments_flag_is_honoured(self):
        self.assertClean("feat(a): x\n\nbody\n# a comment", "--strip-comments")
        self.assertRule("feat(a): x\nbody", "blank-line-before-body", "--no-strip-comments")


class TestTrailerVocabulary(LintTestCase):
    def test_a_mistyped_trailer_alone_is_caught(self):
        """The reference states verbatim that `Reviewed by: Z` is rejected."""
        self.assertRule("fix(pool): raise max conns\n\nThe p99 sat at 1.8s.\n\n"
                        "Reviewed by: Z", "footer-token-whitespace")

    def test_signed_off_by_typed_with_spaces(self):
        self.assertRule("fix: x\n\nSigned off by: Z", "footer-token-whitespace")

    def test_body_prose_beside_a_word_colon_line_is_not_a_footer(self):
        self.assertClean("docs(api): document the retry budget\n\n"
                         "Rate limiting: the budget is 3 retries per request.\n"
                         "Note: the breaker opens after 5 consecutive failures.")

    def test_a_custom_hyphenated_trailer_is_accepted(self):
        self.assertClean("fix: x\n\nDeploy-target: staging")

    def test_breaking_change_in_the_body_is_caught_either_way(self):
        """A trailing footer-shaped paragraph must not change the answer."""
        for tail in ("Note: see docs.", "See the migration guide in docs/migration.md."):
            self.assertRule("feat(api): add v2 of the search endpoint\n\n"
                            "BREAKING CHANGE: v1 is gone.\n\n" + tail,
                            "breaking-change-not-a-footer")


class TestJsonOutput(LintTestCase):
    def test_no_excerpt_applies_to_json(self):
        proc = subprocess.run(
            [sys.executable, LINT, "--stdin", "--format", "json", "--no-excerpt"],
            input="aws_secret_access_key = SENSITIVE", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("SENSITIVE", proc.stdout)
        self.assertIn("header-no-type", proc.stdout)


class TestCli(unittest.TestCase):
    def test_file_argument(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("feat(cache): add write-through path\n")
            path = fh.name
        try:
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)
        finally:
            os.unlink(path)

    def test_missing_file_exits_two(self):
        proc = subprocess.run([sys.executable, LINT, "/nonexistent/msg"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_no_input_exits_two(self):
        proc = subprocess.run([sys.executable, LINT], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_text_output_names_the_rule_and_the_fix(self):
        proc = subprocess.run(
            [sys.executable, LINT, "--stdin", "--label", "commit-message"],
            input="add cache", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("commit-message:1:1:", proc.stdout)
        self.assertIn("[header-no-type]", proc.stdout)
        self.assertIn("fix:", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
