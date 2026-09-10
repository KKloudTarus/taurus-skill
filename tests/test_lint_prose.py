#!/usr/bin/env python3
"""Tests for hooks/lint-prose.py. Run: python3 tests/test_lint_prose.py"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "hooks", "lint-prose.py")


def lint(text, *extra):
    proc = subprocess.run(
        [sys.executable, LINT, "--stdin", "--format", "json", *extra],
        input=text, capture_output=True, text=True, timeout=30,
    )
    findings = json.loads(proc.stdout) if proc.stdout.strip() else []
    return proc.returncode, {f["rule"] for f in findings}, findings


class TestBannedPatterns(unittest.TestCase):
    def assertFlags(self, text, rule, *extra):
        code, rules, findings = lint(text, *extra)
        self.assertIn(rule, rules, f"expected {rule} for {text!r}, got {rules}")
        return findings

    def assertClean(self, text, *extra):
        code, rules, findings = lint(text, *extra)
        self.assertEqual(code, 0, f"expected clean, got {findings}")

    def test_em_dash(self):
        self.assertFlags("Cache hit rate dropped — the TTL was too short.", "em-dash")

    def test_negation_reversal_vietnamese(self):
        self.assertFlags("Đây không phải lỗi mạng, mà là timeout ở tầng pool.", "negation-reversal-vi")

    def test_negation_reversal_vietnamese_semicolon(self):
        self.assertFlags("Không phải vấn đề cấu hình; là bug ở retry policy.", "negation-reversal-vi")

    def test_negation_reversal_english(self):
        self.assertFlags("It's not a network fault, it's a pool timeout.", "negation-reversal-en")

    def test_not_just_but(self):
        self.assertFlags("This is not just a cache, but a write-through buffer.", "negation-reversal-en")

    def test_not_synonymous_vietnamese(self):
        self.assertFlags("Idempotency không đồng nghĩa với retry an toàn.", "not-synonymous")

    def test_meta_opener_vietnamese(self):
        self.assertFlags("Tóm lại, hệ thống chạy ổn định.", "meta-opener")

    def test_meta_opener_english(self):
        self.assertFlags("In summary, the migration succeeded.", "meta-opener")

    def test_filler_opener(self):
        self.assertFlags("Great question! The pool size is 20.", "filler-opener")

    def test_this_is_however(self):
        self.assertFlags("Điều này là an toàn, tuy nhiên consumer cần xử lý lại.", "this-is-however")

    def test_llm_tell(self):
        self.assertFlags("Let's delve into the retry policy.", "llm-tell")
        self.assertFlags("Đáng chú ý là pool đã đầy.", "llm-tell")

    def test_ai_attribution(self):
        self.assertFlags("Co-Authored-By: Claude <noreply@anthropic.com>", "ai-attribution", "--profile", "commit")

    def test_hedge_stack_needs_two(self):
        code, rules, _ = lint("Có thể pool đã đầy.")
        self.assertNotIn("hedge-stack", rules)
        self.assertFlags("Có thể pool tương đối đầy nên có lẽ request bị treo.", "hedge-stack")

    def test_abstract_noun_chain_needs_three(self):
        self.assertFlags(
            "Việc đảm bảo tính nhất quán của quá trình đồng bộ hoá trạng thái là khả năng bắt buộc.",
            "abstract-noun-chain",
        )

    def test_emoji_flagged(self):
        self.assertFlags("Deploy xong 🚀 rồi nhé.", "emoji")

    def test_mini_conclusion_needs_repetition(self):
        one = "Pool đầy. Do đó request treo."
        code, rules, _ = lint(one)
        self.assertNotIn("mini-conclusion", rules)
        many = (
            "Pool đầy ở peak. Do đó request treo lâu hơn.\n\n"
            "Retry chạy ba lần. Vì vậy tải nhân lên gấp ba.\n\n"
            "TTL là 30 giây. Như vậy cache miss dồn vào cùng một thời điểm."
        )
        self.assertFlags(many, "mini-conclusion")


class TestCleanProse(unittest.TestCase):
    def assertClean(self, text, *extra):
        code, rules, findings = lint(text, *extra)
        self.assertEqual(code, 0, f"expected clean, got {findings}")

    def test_plain_technical_prose(self):
        self.assertClean(
            "Pool size is 20. At peak the queue holds 400 requests, so p99 latency reaches 1.8s.\n"
            "Raising the pool to 60 keeps p99 under 300ms in the benchmark."
        )

    def test_plain_vietnamese_prose(self):
        self.assertClean(
            "Pool size hiện là 20. Ở giờ cao điểm queue giữ 400 request nên p99 chạm 1.8s.\n"
            "Nâng pool lên 60 giữ p99 dưới 300ms trong benchmark."
        )

    def test_clean_commit_message(self):
        self.assertClean("feat(inventory): hold seats with row-level lock\n\nReplaces the Redis check.", "--profile", "commit")


class TestSuppression(unittest.TestCase):
    def test_code_fence_is_ignored(self):
        code, rules, _ = lint("Normal line.\n\n```\nvalue — other\n```\n")
        self.assertNotIn("em-dash", rules)

    def test_inline_code_is_ignored(self):
        code, rules, _ = lint("Use the `a — b` token literal.")
        self.assertNotIn("em-dash", rules)

    def test_disable_block(self):
        code, rules, _ = lint("<!-- prose-lint-disable -->\nIt's not X, it's Y.\n<!-- prose-lint-enable -->\n")
        self.assertNotIn("negation-reversal-en", rules)

    def test_disable_line(self):
        code, rules, _ = lint("Bad — line. <!-- prose-lint-disable-line -->\n")
        self.assertNotIn("em-dash", rules)

    def test_url_is_ignored(self):
        code, rules, _ = lint("See https://claude.ai/code for details.", "--profile", "commit")
        self.assertNotIn("ai-attribution", rules)


class TestSourceRepoExemption(unittest.TestCase):
    """The repo that ships this standard documents the tool by name."""

    def test_prose_in_source_repo_may_name_the_tool(self):
        path = os.path.join(ROOT, "tests", ".tmp-source-fixture.md")
        with open(path, "w") as fh:
            fh.write("Install the pack into Claude Code.\n")
        try:
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stdout)
        finally:
            os.remove(path)

    def test_prose_outside_the_source_repo_is_flagged(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "notes.md")
            with open(path, "w") as fh:
                fh.write("Install the pack into Claude Code.\n")
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("ai-attribution", proc.stdout)

    def test_commit_profile_never_takes_the_exemption(self):
        path = os.path.join(ROOT, "tests", ".tmp-source-commit.txt")
        with open(path, "w") as fh:
            fh.write("chore: bump Claude Code config\n")
        try:
            proc = subprocess.run(
                [sys.executable, LINT, "--profile", "commit", path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("ai-attribution", proc.stdout)
        finally:
            os.remove(path)

    def test_stdin_never_takes_the_exemption(self):
        code, rules, _ = lint("Install the pack into Claude Code.")
        self.assertIn("ai-attribution", rules)


class TestCli(unittest.TestCase):
    def test_exit_code_1_on_error(self):
        code, _, _ = lint("Tóm lại, xong.")
        self.assertEqual(code, 1)

    def test_warn_only_passes_by_default(self):
        code, rules, _ = lint("Deploy xong 🚀.")
        self.assertIn("emoji", rules)
        self.assertEqual(code, 0)

    def test_warn_severity_fails(self):
        code, _, _ = lint("Deploy xong 🚀.", "--severity", "warn")
        self.assertEqual(code, 1)

    def test_line_numbers_are_reported(self):
        _, _, findings = lint("line one\nline two\nbad — line\n")
        self.assertEqual(findings[0]["line"], 3)

    def test_no_input_is_usage_error(self):
        proc = subprocess.run([sys.executable, LINT], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 2)

    def test_reads_files_from_argv(self):
        path = os.path.join(ROOT, "tests", ".tmp-lint-fixture.md")
        with open(path, "w") as fh:
            fh.write("Tóm lại, đã xong.\n")
        try:
            proc = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("meta-opener", proc.stdout)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
