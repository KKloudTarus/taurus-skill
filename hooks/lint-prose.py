#!/usr/bin/env python3
"""Prose linter for the taurus writing standard.

Flags the LLM tells the team has banned: em dashes used as connectors,
negation-reversal constructions, meta-conclusions, stacked hedges, filler
openers, and AI attribution. Works on Vietnamese and English text.

Usage:
    lint-prose.py FILE [FILE ...]
    lint-prose.py --stdin [--label NAME]
    lint-prose.py --stdin --profile commit
    lint-prose.py --format json FILE
    lint-prose.py --severity warn FILE     # fail on warnings too

Exit codes: 0 clean, 1 findings at or above the failing severity, 2 usage error.

Suppression:
    <!-- prose-lint-disable -->  ... <!-- prose-lint-enable -->
    any line containing  prose-lint-disable-line
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass

ERROR, WARN = "error", "warn"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    pattern: re.Pattern
    message: str
    fix: str
    profiles: tuple = ("prose", "commit")


def rx(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE | re.UNICODE)


RULES: tuple[Rule, ...] = (
    Rule(
        "ai-attribution",
        ERROR,
        rx(r"co-authored-by:\s*claude|generated with claude|claude\s*code\b|\banthropic\b|claude\.ai/code|\U0001F916"),
        "AI attribution in text that leaves this machine",
        "Remove every Claude/Anthropic mention and the robot emoji.",
    ),
    Rule(
        "em-dash",
        ERROR,
        rx(r"\s—|—\s|—"),
        "em dash used as a prose connector",
        "Use a comma, a period, a colon, or parentheses.",
    ),
    Rule(
        "negation-reversal-vi",
        ERROR,
        rx(r"kh(ô|o)ng ph(ả|a)i\s+[^.;\n]{0,70}?[,;]\s*(m(à|a)\s+)?l(à|a)\b"),
        'negation-reversal: "không phải X, mà là Y"',
        "State Y directly. Drop the X it is being contrasted against.",
    ),
    Rule(
        "negation-reversal-en",
        ERROR,
        rx(r"\b(it|this|that|these|they)\s*(?:'s|'re|\s+is|\s+are|\s+was|\s+were)\s+not\s+(just\s+|merely\s+|only\s+)?"
           r"[^.;\n]{0,70}[,;]\s*(?:(?:it|this|that|these|they)\s*(?:'s|'re|\s+is|\s+are|\s+was|\s+were)|but\s+(?:rather\s+)?|rather\s+)"),
        'negation-reversal: "it\'s not X, it\'s Y"',
        "State Y directly.",
    ),
    Rule(
        "not-synonymous",
        ERROR,
        rx(r"kh(ô|o)ng (đ|d)(ồ|o)ng nghĩa|kh(ô|o)ng c(ó|o) nghĩa l(à|a)|does not mean\b|doesn'?t mean\b|is not the same as\b"),
        'pattern "X không đồng nghĩa Y" / "X does not mean Y"',
        "Say what X actually is.",
    ),
    Rule(
        "meta-opener",
        ERROR,
        rx(r"(?m)^\s*(?:[-*+]\s+|>\s*)?(t(ó|o)m l(ạ|a)i|n(ó|o)i c(á|a)ch kh(á|a)c|n(ó|o)i chung|nh(ì|i)n chung l(à|a)|v(ề|e) c(ơ|o) b(ả|a)n th(ì|i)|in summary|in conclusion|to summari[sz]e|to sum up|overall,|ultimately,|in essence)\b"),
        "meta-commentary opener",
        "Delete the opener and keep the content.",
    ),
    Rule(
        "filler-opener",
        ERROR,
        rx(r"(?m)^\s*(great question|excellent question|c(â|a)u h(ỏ|o)i hay|ch(ắ|a)c ch(ắ|a)n r(ồ|o)i|tuy(ệ|e)t v(ờ|o)i|certainly[,!]|absolutely[,!]|of course[,!])"),
        "filler opener",
        "Answer without the preamble.",
    ),
    Rule(
        "this-is-however",
        ERROR,
        rx(r"(đ|d)i(ề|e)u n(à|a)y (l(à|a)|c(ó|o) nghĩa|cho th(ấ|a)y)[^.\n]{0,80}[,]\s*(song|tuy nhi(ê|e)n|nh(ư|u)ng)\b"),
        'pattern "Điều này là X, song/tuy nhiên Y"',
        "Two plain sentences.",
    ),
    Rule(
        "llm-tell",
        ERROR,
        rx(r"\b(delve|seamless(ly)?|robust and scalable|it'?s worth noting|it is worth noting|(đ|d)(á|a)ng ch(ú|u) (ý|y) l(à|a)|c(ầ|a)n l(ư|u)u (ý|y) r(ằ|a)ng|d(ễ|e) d(à|a)ng nh(ậ|a)n th(ấ|a)y)\b"),
        "stock LLM phrasing",
        "Use plain words.",
    ),
    Rule(
        "hedge-stack",
        WARN,
        rx(r"\b(c(ó|o) th(ể|e)|c(ó|o) l(ẽ|e)|d(ườ|uo)ng nh(ư|u)|t(ươ|uo)ng (đ|d)(ố|o)i|arguably|generally|typically|somewhat|perhaps|possibly|relatively)\b"),
        "stacked hedging in one sentence",
        "Commit to the claim, or name the exact condition that makes it uncertain.",
    ),
    Rule(
        "abstract-noun-chain",
        WARN,
        rx(r"\b(vi(ệ|e)c|s(ự|u)|t(í|i)nh|qu(á|a) tr(ì|i)nh|kh(ả|a) n(ă|a)ng|m(ứ|u)c (đ|d)(ộ|o))\b"),
        "abstract-noun chain",
        "Concrete subject plus verb.",
    ),
    Rule(
        "emoji",
        WARN,
        re.compile(
            "[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]",
            re.UNICODE,
        ),
        "emoji in prose",
        "Remove it unless the reader used emoji first.",
    ),
)

RULES_BY_ID = {r.id: r for r in RULES}

# Rules whose findings only make sense once per sentence, counted, not matched.
COUNTED = {"hedge-stack": 2, "abstract-noun-chain": 3}

CONCLUSION_MARKERS = rx(
    r"^\s*(nh(ư|u) v(ậ|a)y|do (đ|d)(ó|o)|v(ì|i) v(ậ|a)y|v(ì|i) th(ế|e)|t(ừ|u) (đ|d)(ó|o)|"
    r"(đ|d)(â|a)y l(à|a)|(đ|d)i(ề|e)u n(à|a)y (cho th(ấ|a)y|c(ó|o) nghĩa)|"
    r"thus\b|therefore\b|this means\b|this is why\b|which is why\b|in other words\b)"
)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?:])\s+|\n")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
URL = re.compile(r"https?://\S+|\b[\w.-]+@[\w.-]+\.\w+")
MD_LINK_TARGET = re.compile(r"\]\([^)]*\)")


@dataclass
class Finding:
    path: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    fix: str
    excerpt: str


def mask(text: str) -> list[str]:
    """Blank out code fences, inline code, URLs and suppressed regions.

    Replaces masked characters with spaces so line and column numbers survive.
    """
    lines = text.splitlines()
    out, in_fence, suppressed = [], False, False
    for line in lines:
        stripped = line.strip()
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(" " * len(line))
            continue
        if "prose-lint-disable-line" in line:
            out.append(" " * len(line))
            continue
        if "prose-lint-disable" in stripped and "line" not in stripped:
            suppressed = True
            out.append(" " * len(line))
            continue
        if "prose-lint-enable" in stripped:
            suppressed = False
            out.append(" " * len(line))
            continue
        if in_fence or suppressed:
            out.append(" " * len(line))
            continue
        masked = line
        for pattern in (INLINE_CODE, URL, MD_LINK_TARGET):
            masked = pattern.sub(lambda m: " " * len(m.group(0)), masked)
        # Indented code blocks.
        if line.startswith("    ") and not line.lstrip().startswith(("-", "*", "+", "|", ">", "1.")):
            masked = " " * len(line)
        out.append(masked)
    return out


def line_of(offset: int, starts: list[int]) -> tuple[int, int]:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1, offset - starts[lo] + 1


def in_source_repo(path: str) -> bool:
    """True when the file lives in the repo that ships this standard.

    That repo documents the tooling by name, so the attribution rule would fire on
    its own README. Commit messages stay covered everywhere: the commit profile
    never takes this exemption.
    """
    try:
        current = os.path.dirname(os.path.abspath(path))
    except (OSError, ValueError):
        return False
    while True:
        if os.path.exists(os.path.join(current, ".taurus-skill-source")):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def scan(text: str, path: str, profile: str) -> list[Finding]:
    exempt_attribution = profile == "prose" and path != "<stdin>" and in_source_repo(path)
    lines = mask(text)
    masked = "\n".join(lines)
    starts, pos = [], 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    findings: list[Finding] = []
    for rule in RULES:
        if profile not in rule.profiles or rule.id in COUNTED:
            continue
        if rule.id == "ai-attribution" and exempt_attribution:
            continue
        for m in rule.pattern.finditer(masked):
            ln, col = line_of(m.start(), starts)
            findings.append(Finding(
                path, ln, col, rule.id, rule.severity, rule.message, rule.fix,
                m.group(0).strip()[:60],
            ))

    # Counted rules fire per sentence, above a density threshold.
    for sentence, offset in sentences(masked):
        for rule_id, threshold in COUNTED.items():
            rule = RULES_BY_ID[rule_id]
            if profile not in rule.profiles:
                continue
            hits = rule.pattern.findall(sentence)
            if len(hits) >= threshold:
                ln, col = line_of(offset, starts)
                findings.append(Finding(
                    path, ln, col, rule.id, rule.severity,
                    f"{rule.message} ({len(hits)} in one sentence)", rule.fix,
                    sentence.strip()[:60],
                ))

    findings.extend(mini_conclusions(masked, path, starts))
    findings.sort(key=lambda f: (f.line, f.col, f.rule))
    return findings


def sentences(text: str) -> list[tuple[str, int]]:
    result, pos = [], 0
    for part in SENTENCE_SPLIT.split(text):
        if part is None:
            continue
        idx = text.find(part, pos)
        if idx < 0:
            idx = pos
        if part.strip():
            result.append((part, idx))
        pos = idx + len(part)
    return result


def mini_conclusions(text: str, path: str, starts: list[int]) -> list[Finding]:
    """Flag the habit of ending every paragraph with a summary sentence."""
    hits = []
    pos = 0
    for block in text.split("\n\n"):
        offset = text.find(block, pos)
        pos = offset + len(block)
        stripped = block.strip()
        if not stripped or stripped.startswith(("|", "#", "-", "*", ">", "1.")):
            continue
        parts = [s for s, _ in sentences(block)]
        if len(parts) < 2:
            continue
        last = parts[-1]
        if CONCLUSION_MARKERS.match(last.strip()):
            local = block.find(last)
            ln, col = line_of(offset + max(local, 0), starts)
            hits.append(Finding(
                path, ln, col, "mini-conclusion", WARN,
                "paragraph closes with a summary sentence",
                "Delete it. Keep at most one conclusion per document.",
                last.strip()[:60],
            ))
    if len(hits) < 2:
        return []
    return hits


FINDING_LIMIT = 50


def render_text(findings: list[Finding], excerpts: bool = True) -> str:
    out = []
    shown = findings[:FINDING_LIMIT]
    for f in shown:
        out.append(f"{f.path}:{f.line}:{f.col}: {f.severity}: [{f.rule}] {f.message}")
        if excerpts:
            out.append(f"    found: {f.excerpt!r}")
        out.append(f"    fix:   {f.fix}")
    if len(findings) > len(shown):
        out.append(f"... and {len(findings) - len(shown)} more findings")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--label", default="<stdin>")
    ap.add_argument("--profile", default="prose", choices=["prose", "commit"])
    ap.add_argument("--format", default="text", choices=["text", "json"])
    ap.add_argument("--no-excerpt", action="store_true",
                    help="report rules without quoting the text")
    ap.add_argument("--severity", default="error", choices=["error", "warn"],
                    help="lowest severity that fails the run")
    args = ap.parse_args(argv)

    inputs: list[tuple[str, str]] = []
    if args.stdin:
        inputs.append((args.label, sys.stdin.read()))
    for path in args.files:
        try:
            with open(path, encoding="utf-8") as fh:
                inputs.append((path, fh.read()))
        except OSError as exc:
            sys.stderr.write(f"cannot read {path}: {exc}\n")
            return 2
    if not inputs:
        ap.print_usage(sys.stderr)
        return 2

    findings: list[Finding] = []
    for path, text in inputs:
        findings.extend(scan(text, path, args.profile))

    failing = [f for f in findings if args.severity == "warn" or f.severity == ERROR]

    if args.format == "json":
        rows = []
        for f in findings:
            row = dict(f.__dict__)
            if args.no_excerpt:
                row["excerpt"] = ""
            rows.append(row)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif findings:
        print(render_text(findings, not args.no_excerpt))

    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
