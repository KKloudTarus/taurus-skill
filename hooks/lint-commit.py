#!/usr/bin/env python3
"""Validate a commit message against Conventional Commits 1.0.0.

Grammar enforced (https://www.conventionalcommits.org/en/v1.0.0/):

    <type>[optional scope][!]: <description>

    [optional body]

    [optional footer(s)]

This file owns the grammar. hooks/guard-git.py shells out to it for `git commit`,
and repos wire it as a commit-msg hook. Add a rule here, nowhere else.

Usage:
    lint-commit.py FILE...                     validate each file as one message
    lint-commit.py --stdin                     validate a message on stdin
    lint-commit.py --stdin --pr-title          validate a single header line
    lint-commit.py --stdin --format json       machine-readable findings
    lint-commit.py --no-excerpt                report rules without quoting the text

Comment lines are stripped from a FILE argument, matching git's editor cleanup, and
kept on --stdin, matching git's `whitespace` cleanup for -m and -F. Override with
--strip-comments or --no-strip-comments.

Exit: 0 clean, 1 findings at or above --severity, 2 usage or read error.
"""

import argparse
import re
import sys

ERROR = "error"
WARN = "warn"

# feat and fix are mandated by the spec. The rest is the Angular set the spec
# points at, fixed here so changelog tooling has a closed vocabulary.
TYPES = (
    "feat", "fix", "build", "chore", "ci", "docs",
    "perf", "refactor", "revert", "style", "test",
)

BREAKING_TOKENS = ("BREAKING CHANGE", "BREAKING-CHANGE")

HEADER = re.compile(
    r"^(?P<type>[A-Za-z][A-Za-z]*)"
    r"(?:\((?P<scope>[^()]*)\))?"
    r"(?P<bang>!)?"
    r": (?P<desc>.*)$"
)

# Separator is ":<space>" or "<space>#", per the spec's footer rule.
FOOTER = re.compile(
    r"^(?P<token>BREAKING CHANGE|BREAKING-CHANGE|[A-Za-z][A-Za-z0-9-]*)"
    r"(?::[ ]|[ ]#)"
    r"(?P<value>.*)$"
)

# "Reviewed by: Z" instead of "Reviewed-by: Z". Bounded to two or three short words
# so a body sentence that happens to carry a colon is not read as a trailer.
WHITESPACE_TOKEN = re.compile(r"^(?P<token>[A-Za-z][A-Za-z0-9]*(?:[ ][A-Za-z][A-Za-z0-9]*){1,2}):[ ]\S")
TOKEN_LIMIT = 24

# `Word: value` is also how ordinary prose writes a sentence, so a bare token counts
# as a footer only when it is a known trailer. A hyphenated token (`Reviewed-by`,
# `Deploy-target`) is unambiguous, since prose does not spell a phrase that way.
TRAILER_TOKENS = frozenset({
    "refs", "ref", "closes", "close", "fixes", "resolves", "resolve", "cc",
    "related", "reverts", "bug", "issue", "ticket", "see", "link",
})
# The hyphenated trailers git and this pack actually use. A phrase is reported as a
# mistyped trailer only when its hyphenated form is one of these, so body prose like
# `Rate limiting: ...` stays prose.
TRAILER_HYPHENATED = frozenset({
    "reviewed-by", "signed-off-by", "co-authored-by", "acked-by", "tested-by",
    "reported-by", "suggested-by", "helped-by", "mentored-by", "part-of",
    "change-id", "depends-on", "see-also", "breaking-change",
})

BREAKING_ANY_CASE = re.compile(r"^(?P<token>breaking[ -]change)(?P<rest>.*)$", re.I)
BREAKING_SEPARATOR = re.compile(r"^:[ ](?P<value>.*)$")

SCOPE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
# Anchored and unpadded. An unbounded \s* here backtracks quadratically on a long
# run of whitespace, and a PR title can come from an uncapped forge.
PR_SUFFIX = re.compile(r"\(#\d{1,10}\)\Z")
SCISSORS = re.compile(r"^\s*(#\s*)?-{2,}\s*>8\s*-{2,}")

# Messages git generates or reserves. The spec leaves them to tooling.
GENERATED = (
    re.compile(r"^Merge[ ]"),
    re.compile(r"^Revert[ ]\""),
    re.compile(r"^(fixup|squash|amend)![ ]"),
)

HEADER_LIMIT = 72
FINDING_LIMIT = 50


class Finding:
    __slots__ = ("label", "line", "col", "rule", "severity", "message", "fix", "excerpt")

    def __init__(self, label, line, col, rule, severity, message, fix, excerpt=""):
        self.label, self.line, self.col = label, line, col
        self.rule, self.severity = rule, severity
        self.message, self.fix, self.excerpt = message, fix, excerpt

    def as_dict(self, excerpts=True):
        out = {k: getattr(self, k) for k in self.__slots__}
        if not excerpts:
            out["excerpt"] = ""
        return out


def strip_comments(text: str, strip_hash: bool = True) -> list[str]:
    """Normalize line endings, drop the scissors tail, optionally drop # comments.

    The subject is never dropped. git's editor block always sits below it, and for
    -m and -F git's cleanup is `whitespace`, which keeps a leading # as the subject.
    """
    out, seen_subject = [], False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if SCISSORS.match(line):
            break
        if strip_hash and seen_subject and line.startswith("#"):
            continue
        if line.strip():
            seen_subject = True
        out.append(line.rstrip())
    while out and not out[-1].strip():
        out.pop()
    # git drops leading blank lines and takes the first non-blank line as the subject.
    while out and not out[0].strip():
        out.pop(0)
    return out


def is_generated(header: str) -> bool:
    return any(p.match(header) for p in GENERATED)


def paragraphs(lines: list[str], start: int) -> list[tuple[int, list[str]]]:
    """Blocks of non-blank lines after `start`, each with its 1-based first line."""
    blocks, buf, first = [], [], None
    for idx in range(start, len(lines)):
        line = lines[idx]
        if line.strip():
            if first is None:
                first = idx + 1
            buf.append(line)
            continue
        if buf:
            blocks.append((first, buf))
            buf, first = [], None
    if buf:
        blocks.append((first, buf))
    return blocks


def is_trailer(token: str) -> bool:
    normalized = token.strip().lower()
    if normalized in ("breaking change", "breaking-change"):
        return True
    if "-" in normalized:
        return True
    return normalized in TRAILER_TOKENS


def mistyped_token(line: str) -> str | None:
    """A trailer written with spaces where the spec requires hyphens."""
    if starts_footer(line):
        return None
    hit = WHITESPACE_TOKEN.match(line)
    if not hit or len(hit.group("token")) > TOKEN_LIMIT:
        return None
    token = hit.group("token")
    # Only when the hyphenated form is a trailer git actually uses. The generic
    # "a hyphen means a trailer" rule must not apply here: it would turn every
    # two-word sentence opener into a finding.
    hyphenated = token.replace(" ", "-").lower()
    return token if hyphenated in TRAILER_HYPHENATED else None


def starts_footer(line: str) -> bool:
    if BREAKING_ANY_CASE.match(line):
        return True
    hit = FOOTER.match(line)
    return bool(hit and is_trailer(hit.group("token")))


def block_is_footers(block: list[str]) -> bool:
    """A block opens the footer section, or is a trailer typed with spaces."""
    return starts_footer(block[0]) or bool(mistyped_token(block[0]))


def footer_section(blocks: list[tuple[int, list[str]]]) -> list[tuple[int, list[str]]]:
    """The trailing run of blocks that are footers.

    The spec allows a footer value to span newlines and says parsing stops at the
    next valid token. A blank line between footers is a valid separator, so the
    footer section can be several blocks, not only the last one.
    """
    idx = len(blocks)
    while idx > 0 and block_is_footers(blocks[idx - 1][1]):
        idx -= 1
    return blocks[idx:]


def check_header(header: str, label: str, out: list[Finding]) -> re.Match | None:
    def add(rule, severity, message, fix, col=1, excerpt=None):
        out.append(Finding(label, 1, col, rule, severity, message, fix,
                           header[:72] if excerpt is None else excerpt))

    match = HEADER.match(header)
    if not match:
        if header != header.lstrip():
            add("header-leading-space", ERROR,
                "the subject starts with whitespace",
                "Start the line with the type: feat(scope): description")
        elif ":" not in header:
            add("header-no-type", ERROR,
                "the subject carries no Conventional Commits type prefix",
                f"Write <type>[(scope)][!]: <description>. Types: {', '.join(TYPES)}")
        elif re.match(r"^[A-Za-z]+(\([^()]*\))?!?:\S", header):
            add("header-no-space", ERROR,
                "the colon after the type is not followed by a space",
                "The spec requires a terminal colon and space: feat: add X")
        elif re.match(r"^[A-Za-z]+(\([^()]*\))?!?:$", header):
            add("header-no-description", ERROR,
                "the subject has a type prefix and no description",
                "A description must follow the colon and space.")
        else:
            add("header-malformed", ERROR,
                "the subject does not match <type>[(scope)][!]: <description>",
                f"Rewrite it as <type>[(scope)][!]: <description>. Types: {', '.join(TYPES)}")
        return None

    ctype = match.group("type")
    if ctype != ctype.lower():
        add("type-case", ERROR,
            f"the type `{ctype}` is not lowercase",
            "Write the type in lowercase. The spec allows any casing and asks for "
            "consistency; this pack fixes it to lowercase.", excerpt=ctype)
    if ctype.lower() not in TYPES:
        add("type-unknown", ERROR,
            f"`{ctype}` is not one of the allowed types",
            f"Use one of: {', '.join(TYPES)}.", excerpt=ctype)

    if match.group("scope") is not None:
        scope = match.group("scope")
        col = header.index("(") + 2
        if not scope.strip():
            add("scope-empty", ERROR,
                "the scope parentheses are empty",
                "Name the section of the codebase, or drop the parentheses.",
                col=col, excerpt="()")
        elif not SCOPE.match(scope):
            add("scope-format", ERROR,
                f"the scope `{scope}` is not a lowercase noun",
                "A scope is one lowercase noun: letters, digits, . _ / - and no spaces.",
                col=col, excerpt=scope)

    desc = match.group("desc")
    col = header.index(": ") + 3
    if desc[0].isspace():
        add("description-leading-space", ERROR,
            "the description starts with extra whitespace",
            "Exactly one space follows the colon.", col=col, excerpt=desc[:10])
    if desc.rstrip().endswith(".") and not desc.rstrip().endswith(".."):
        add("description-period", ERROR,
            "the description ends with a period",
            "Drop the trailing period.", col=col + len(desc) - 1, excerpt=desc[-20:])
    if desc[:1].isupper() and not re.match(r"^[A-Z]{2,}\b", desc):
        add("description-case", WARN,
            "the description starts with a capital letter",
            "Start lowercase so subjects read the same across the log.",
            col=col, excerpt=desc[:20])

    if len(header) > HEADER_LIMIT:
        add("header-too-long", ERROR,
            f"the subject is {len(header)} characters, over the {HEADER_LIMIT} limit",
            "Shorten the description. Detail belongs in the body.",
            col=HEADER_LIMIT + 1)

    return match


def check_body(lines: list[str], label: str, out: list[Finding]) -> None:
    if len(lines) < 2:
        return
    if lines[1].strip():
        out.append(Finding(
            label, 2, 1, "blank-line-before-body", ERROR,
            "the body does not begin one blank line after the description",
            "Insert a blank line between the subject and the body.",
            lines[1][:60],
        ))


def check_breaking_line(line: str, lineno: int, label: str, out: list[Finding]) -> None:
    hit = BREAKING_ANY_CASE.match(line)
    token, rest = hit.group("token"), hit.group("rest")
    if token not in BREAKING_TOKENS:
        out.append(Finding(
            label, lineno, 1, "breaking-change-case", ERROR,
            f"the breaking-change token `{token}` is not uppercase",
            "The spec requires BREAKING CHANGE (or BREAKING-CHANGE) in uppercase.",
            line[:60],
        ))
        return
    sep = BREAKING_SEPARATOR.match(rest)
    if rest.strip() in ("", ":") or (sep and not sep.group("value").strip()):
        out.append(Finding(
            label, lineno, 1, "breaking-change-empty", ERROR,
            "the BREAKING CHANGE footer has no description",
            "State what breaks and what callers must change.",
            line[:60],
        ))
        return
    if not sep:
        out.append(Finding(
            label, lineno, 1, "breaking-change-separator", ERROR,
            "the BREAKING CHANGE token is not followed by a colon and a space",
            "Write `BREAKING CHANGE: <description>`. The spec fixes that separator.",
            line[:60],
        ))


def check_footers(lines: list[str], has_bang: bool, label: str, out: list[Finding]) -> None:
    section = footer_section(paragraphs(lines, 1))
    footer_lines = set()
    for first_line, block in section:
        for offset in range(len(block)):
            footer_lines.add(first_line + offset)

    breaking_seen = False

    for first_line, block in section:
        for offset, line in enumerate(block):
            lineno = first_line + offset
            if BREAKING_ANY_CASE.match(line):
                check_breaking_line(line, lineno, label, out)
                breaking_seen = True
                continue
            token = mistyped_token(line)
            if token:
                out.append(Finding(
                    label, lineno, 1, "footer-token-whitespace", ERROR,
                    f"the footer token `{token}` contains whitespace",
                    f"Write `{token.replace(' ', '-')}:`. A footer token uses - in place "
                    "of spaces.",
                    line[:60],
                ))

    # A breaking-change footer buried in the body is not a footer.
    for offset, line in enumerate(lines):
        if offset == 0 or (offset + 1) in footer_lines:
            continue
        if BREAKING_ANY_CASE.match(line):
            out.append(Finding(
                label, offset + 1, 1, "breaking-change-not-a-footer", ERROR,
                "BREAKING CHANGE appears outside the footer section",
                "Move it to the footer block, after the body.",
                line[:60],
            ))
            breaking_seen = True

    if has_bang and not breaking_seen:
        out.append(Finding(
            label, 1, 1, "breaking-change-undocumented", WARN,
            "the subject carries ! and no BREAKING CHANGE footer explains it",
            "The spec allows the description alone. Add the footer when callers need the "
            "migration steps.",
            lines[0][:60],
        ))


def lint(text: str, label: str = "<stdin>", pr_title: bool = False,
         strip_hash: bool = True) -> list[Finding]:
    lines = strip_comments(text, strip_hash)
    if not lines or not lines[0].strip():
        return []

    if pr_title:
        lines = [PR_SUFFIX.sub("", lines[0]).rstrip()]

    header = lines[0]
    if is_generated(header):
        return []

    out: list[Finding] = []
    match = check_header(header, label, out)
    check_body(lines, label, out)
    check_footers(lines, bool(match and match.group("bang")), label, out)
    out.sort(key=lambda f: (f.line, f.col, f.rule))
    return out


def render(findings: list[Finding], excerpts: bool = True) -> str:
    out = []
    shown = findings[:FINDING_LIMIT]
    for f in shown:
        out.append(f"{f.label}:{f.line}:{f.col}: {f.severity}: [{f.rule}] {f.message}")
        if excerpts and f.excerpt:
            out.append(f"    found: {f.excerpt!r}")
        out.append(f"    fix:   {f.fix}")
    if len(findings) > len(shown):
        out.append(f"... and {len(findings) - len(shown)} more findings")
    return "\n".join(out)


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--label", default="<stdin>")
    ap.add_argument("--pr-title", action="store_true",
                    help="validate one header line, ignoring a trailing (#123)")
    ap.add_argument("--format", default="text", choices=["text", "json"])
    ap.add_argument("--no-excerpt", action="store_true",
                    help="report rules without quoting the message text")
    ap.add_argument("--strip-comments", dest="strip_comments", action="store_true",
                    default=None, help="drop # lines (git's editor cleanup)")
    ap.add_argument("--no-strip-comments", dest="strip_comments", action="store_false",
                    help="keep # lines (git's cleanup for -m and -F)")
    ap.add_argument("--severity", default="error", choices=["error", "warn"],
                    help="lowest severity that fails the run")
    args = ap.parse_args(argv)

    # git keeps # lines for -m and -F, and drops them for an editor message. stdin
    # carries the former, a file argument is the commit-msg hook's editor buffer.
    inputs: list[tuple[str, str, bool]] = []
    if args.stdin:
        strip = False if args.strip_comments is None else args.strip_comments
        inputs.append((args.label, sys.stdin.read(), strip))
    for path in args.files:
        strip = True if args.strip_comments is None else args.strip_comments
        try:
            inputs.append((path, read_text(path), strip))
        except OSError as exc:
            sys.stderr.write(f"cannot read {path}: {exc}\n")
            return 2
    if not inputs:
        ap.print_usage(sys.stderr)
        return 2

    findings: list[Finding] = []
    for label, text, strip in inputs:
        findings.extend(lint(text, label, args.pr_title, strip))

    failing = [f for f in findings if args.severity == "warn" or f.severity == ERROR]

    if args.format == "json":
        import json
        print(json.dumps([f.as_dict(not args.no_excerpt) for f in findings],
                         ensure_ascii=False, indent=2))
    elif findings:
        print(render(findings, not args.no_excerpt))

    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
