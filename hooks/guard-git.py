#!/usr/bin/env python3
"""PreToolUse guard for Bash git commands.

Blocks four classes of mistake:
  1. AI attribution in commit messages (Claude / Anthropic / Co-Authored-By / robot emoji).
  2. Commit messages that break the writing standard or Conventional Commits 1.0.0.
  3. Staging or committing .claude/, CLAUDE.md, AGENTS.md, .mcp.json.
  4. Pushing a range whose commits touch those paths.

Design note. This guard reads a command string that bash and git will each parse by
their own rules. Three parsers never fully agree, so two things hold here:

  * Quoting state comes from hooks/shellscan.py, a real lexer, never from a regex
    over the raw text. Guessing at it produced both false blocks and real bypasses.
  * Where the guard cannot read a command with confidence it BLOCKS and says why.

It is still the fast layer, not the control of record. That is the repo-side
commit-msg, pre-commit, and pre-push hooks in githooks/, which see what git actually
assembled and cannot be spelled around. install.sh wires them globally.

The repo that hosts this standard opts out of the path rules via a
.taurus-skill-source marker at its root. The message rules apply everywhere.

Contract: reads the PreToolUse JSON payload on stdin. Exit 0 allows, exit 2 blocks
and shows stderr to the model.
"""

import json
import os
import re
import shlex
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shellscan  # noqa: E402

PRIVATE_PATHS = ("CLAUDE.md", "AGENTS.md", ".claude", ".mcp.json")

ATTRIBUTION_PATTERNS = (
    re.compile(r"co-authored-by:.*(claude|anthropic|noreply@anthropic)", re.I),
    re.compile(r"\bgenerated with\b.*\bclaude\b", re.I),
    re.compile(r"\bclaude\s*code\b", re.I),
    re.compile(r"\banthropic\b", re.I),
    re.compile(r"claude\.ai/code", re.I),
    re.compile(r"\U0001F916"),  # robot face
)

SHELL_BOUNDARY = set(";\n|&()`")

# Shell keywords and grouping tokens that can precede a command in its segment.
KEYWORDS = {"if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done",
            "case", "esac", "in", "{", "}", "!", "function", "select", "coproc", "time",
            "&&", "||"}

# Commands that wrap another command. Their own flags are skipped too.
WRAPPERS = {"sudo", "env", "time", "nice", "ionice", "command", "timeout",
            "stdbuf", "nohup", "setsid", "doas", "chrt", "taskset"}

NESTED_SHELL = re.compile(r"\b(?:eval|xargs|(?:ba|z|da|k)?sh\s+-c)\b")
SEGMENT_END = re.compile(r"[;\n|]|&&|\|\|")
DURATION = re.compile(r"^\d+[smhd]?$")

WRITE_VERBS = ("commit", "add", "stage", "push", "am", "rebase", "cherry-pick",
               "merge", "tag", "revert", "rm", "mv", "restore", "apply", "stash",
               "update-index", "update-ref")
RAW_GIT_WRITE = re.compile(r"\bgit\b.*?\b(?:" + "|".join(WRITE_VERBS) + r")\b", re.S)

# Anything that could rewrite a message file inside the same command line.
REDIRECTION = re.compile(r"(?:^|\s)(?:>|>>|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i)")

# git's own options, before the subcommand.
GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                      "--exec-path", "--super-prefix", "--config-env",
                      "--attr-source", "--list-cmds"}
GLOBAL_BOOL_FLAGS = {"-p", "-P", "--paginate", "--no-pager", "--bare", "--version",
                     "--help", "-h", "-v", "--literal-pathspecs", "--glob-pathspecs",
                     "--noglob-pathspecs", "--icase-pathspecs", "--no-replace-objects",
                     "--no-optional-locks", "--no-lazy-fetch", "--no-advice",
                     "--html-path", "--man-path", "--info-path"}

# `git commit` options that always consume a value.
COMMIT_VALUE_LONG = ("--message", "--file", "--trailer", "--reuse-message",
                     "--reedit-message", "--author", "--date", "--cleanup",
                     "--fixup", "--squash", "--pathspec-from-file", "--template")
COMMIT_VALUE_SHORT = {"m": "--message", "F": "--file", "C": "--reuse-message",
                      "c": "--reedit-message", "t": "--template"}
# Options git declares PARSE_OPT_OPTARG: a value only when stuck to the option.
COMMIT_OPTARG_LONG = ("--untracked-files", "--gpg-sign")
COMMIT_OPTARG_SHORT = {"u", "S"}

NO_VERIFY = {"-n", "--no-verify"}

MESSAGE_LIMIT = 64 * 1024
ALIAS_DEPTH = 10
FORBIDDEN_ROOTS = ("/proc", "/sys", "/dev")

STAGING_SUBS = ("add", "update-index")

SUBCOMMANDS = {
    "add", "am", "apply", "archive", "bisect", "blame", "branch", "cat-file",
    "check-ignore", "checkout", "cherry-pick", "clean", "clone", "commit", "config",
    "describe", "diff", "fetch", "for-each-ref", "format-patch", "fsck", "gc", "grep",
    "help", "init", "log", "ls-files", "ls-remote", "ls-tree", "merge", "mv", "notes",
    "pull", "push", "range-diff", "rebase", "reflog", "remote", "reset", "restore",
    "revert", "rev-list", "rev-parse", "rm", "shortlog", "show", "sparse-checkout",
    "stash", "status", "submodule", "switch", "symbolic-ref", "tag", "update-index",
    "update-ref", "version", "worktree", "write-tree",
}


def fail(reason: str) -> None:
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)


def read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def git_out(args: list[str], timeout: int = 10) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return out.stdout if out.returncode == 0 else None


def repo_root(cwd: str) -> str | None:
    out = git_out(["-C", cwd, "rev-parse", "--show-toplevel"], timeout=5)
    return out.strip() if out and out.strip() else None


def is_source_repo(root: str | None) -> bool:
    return bool(root) and os.path.exists(os.path.join(root, ".taurus-skill-source"))


# --- reading the command ----------------------------------------------------


def hidden_git_write(command: str) -> str | None:
    """A shell construct that runs git where the guard cannot read it.

    Every test runs against what bash will actually interpret, so the word `eval`
    inside a commit message is text, and a substitution between two apostrophes
    inside a double-quoted string is still a substitution.
    """
    sc = shellscan.scan(command)

    if (sc.unreadable_heredoc or sc.unterminated_heredoc) and RAW_GIT_WRITE.search(command):
        return ("a heredoc whose delimiter or terminator cannot be determined, which "
                "leaves the rest of the command unreadable")

    for start, end in shellscan.substitutions(sc):
        if RAW_GIT_WRITE.search(sc.text[start:end]):
            return "command substitution, which runs git out of the guard's view"

    if shellscan.ansi_c_quotes(sc) and RAW_GIT_WRITE.search(command):
        return "ANSI-C quoting, which bash expands and the guard cannot"

    for start, end in shellscan.code_spans(sc):
        span = sc.text[start:end]
        for hit in NESTED_SHELL.finditer(span):
            # What the nested shell receives, quoted argument included, up to the next
            # command boundary. A later `git add` in the pipeline is its own command.
            begin = start + hit.start()
            rest = sc.text[begin:segment_end(sc, begin)]
            if RAW_GIT_WRITE.search(rest):
                return f"`{hit.group(0)}`, which runs git out of the guard's view"

    return None


def segment_end(sc, pos: int) -> int:
    """Offset of the next unquoted command boundary at or after pos."""
    text = sc.text
    i = pos
    while i < len(text):
        if sc.state(i) == shellscan.NORMAL:
            if text[i] in ";\n|" or text.startswith("&&", i) or text.startswith("||", i):
                return i
        i += 1
    return len(text)


def expanded_in(command: str, start: int, end: int) -> bool:
    """True when the shell builds part of THIS command span from an expansion.

    The guard reads the pre-expansion text, so a message assembled this way is not
    the message git receives. Both `$(...)` and `$VAR` count: a variable holding a
    commit message hides it just as well. A single-quoted expansion is literal and
    does not count, and an expansion in a different command on the line is not this
    one's.
    """
    sc = shellscan.scan(command)
    for a, b in shellscan.substitutions(sc) + shellscan.parameter_expansions(sc):
        if a < end and b > start:
            return True
    return False


def without_heredocs(command: str) -> str:
    """Blank heredoc bodies so tokenizing never reads data as arguments."""
    sc = shellscan.scan(command)
    return "".join(" " if state == shellscan.HEREDOC else ch
                   for ch, state in zip(sc.text, sc.mask))


def split_spans(command: str) -> list[tuple[str, int, int]]:
    """Split into commands on unquoted ; | & ( ) ` and newlines, keeping offsets."""
    spans, start = [], 0
    single = double = escaped = False
    for i, ch in enumerate(command):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and not single:
            escaped = True
            continue
        if ch == "'" and not double:
            single = not single
            continue
        if ch == '"' and not single:
            double = not double
            continue
        if not single and not double and ch in SHELL_BOUNDARY:
            spans.append((command[start:i], start, i))
            start = i + 1
    spans.append((command[start:], start, len(command)))
    return [(text, a, b) for text, a, b in spans if text.strip()]


def split_shell(command: str) -> list[str]:
    return [text.strip() for text, _, _ in split_spans(command)]


def strip_prefix(tokens: list[str]) -> list[str]:
    """Drop shell keywords, env assignments, and wrapper commands with their flags."""
    wrapped = False
    while tokens:
        head = os.path.basename(tokens[0])
        if tokens[0] in KEYWORDS:
            tokens = tokens[1:]
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]) or head in WRAPPERS:
            tokens = tokens[1:]
            wrapped = True
            continue
        break
    if wrapped and tokens and os.path.basename(tokens[0]) != "git":
        # Consume the wrapper's own flags, each flag's value, and one duration, then
        # the next token is the wrapped command. Scanning further would misread the
        # arguments of a different command as git's.
        while tokens:
            if tokens[0].startswith("-"):
                tokens = tokens[1:]
                if tokens and not tokens[0].startswith("-") \
                        and os.path.basename(tokens[0]) != "git":
                    tokens = tokens[1:]
                continue
            if DURATION.match(tokens[0]):
                tokens = tokens[1:]
                continue
            break
    return tokens


def segments(command: str) -> list[tuple[list[str], int, int]]:
    """Git invocations in the line, as (tokens, start offset, end offset)."""
    result = []
    for raw, start, end in split_spans(without_heredocs(command)):
        raw = raw.strip()
        if not raw:
            continue
        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()
        tokens = strip_prefix(tokens)
        if tokens and os.path.basename(tokens[0]) == "git":
            result.append((tokens, start, end))
    return result


def git_subcommand(tokens: list[str]) -> tuple[str | None, list[str], dict, str | None, bool]:
    """Return (subcommand, args, inline config, retargeted repo dir, parsed cleanly).

    An unrecognized global flag means the guard cannot tell where the subcommand
    starts, so it reports parsed_cleanly=False and the caller fails closed.
    """
    inline: dict[str, str] = {}
    retarget: str | None = None
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-"):
            return tok, tokens[i + 1:], inline, retarget, True
        if tok.startswith("-c") and len(tok) > 2 and not tok.startswith("--"):
            key, _, value = tok[2:].partition("=")
            inline[key] = value
            i += 1
            continue
        if tok.startswith("-C") and len(tok) > 2:
            retarget = tok[2:]
            i += 1
            continue
        if tok.startswith("--") and "=" in tok:
            name, _, value = tok.partition("=")
            if name not in GLOBAL_VALUE_FLAGS and name not in GLOBAL_BOOL_FLAGS:
                return None, [], inline, retarget, False
            if name == "--config-env":
                key, _, var = value.partition("=")
                if key.startswith("alias."):
                    return None, [], inline, retarget, False
                inline[key] = os.environ.get(var, "")
            elif name in ("--git-dir", "--work-tree"):
                retarget = value
            i += 1
            continue
        if tok in GLOBAL_VALUE_FLAGS:
            value = tokens[i + 1] if i + 1 < len(tokens) else ""
            if tok == "-c":
                key, _, val = value.partition("=")
                inline[key] = val
            elif tok == "--config-env":
                key, _, var = value.partition("=")
                if key.startswith("alias."):
                    return None, [], inline, retarget, False
                inline[key] = os.environ.get(var, "")
            elif tok in ("-C", "--git-dir", "--work-tree"):
                retarget = value
            i += 2
            continue
        if tok in GLOBAL_BOOL_FLAGS:
            i += 1
            continue
        return None, [], inline, retarget, False
    return None, [], inline, retarget, True


def alias_value(root: str | None, name: str, inline: dict) -> str | None:
    if f"alias.{name}" in inline:
        return inline[f"alias.{name}"]
    if not root:
        return None
    out = git_out(["-C", root, "config", "--get", f"alias.{name}"], timeout=5)
    return out.strip() if out and out.strip() else None


def resolve_alias(root: str | None, sub: str, inline: dict) -> tuple[str, list[str], bool]:
    """Expand git aliases recursively. Returns (subcommand, prefix args, readable)."""
    prefix: list[str] = []
    seen: set[str] = set()
    for _ in range(ALIAS_DEPTH):
        if sub in SUBCOMMANDS or sub in seen:
            return sub, prefix, True
        seen.add(sub)
        expansion = alias_value(root, sub, inline)
        if not expansion:
            return sub, prefix, True
        if expansion.startswith("!"):
            return sub, prefix, False  # shell alias, contents unknowable here
        try:
            parts = shlex.split(expansion)
        except ValueError:
            return sub, prefix, False
        if not parts:
            return sub, prefix, True
        sub, prefix = parts[0], parts[1:] + prefix
    return sub, prefix, False


def unique_long(name: str, table) -> str | None:
    """git accepts any unambiguous prefix of a long option."""
    if name in table:
        return name
    hits = [opt for opt in table if opt.startswith(name)]
    return hits[0] if len(hits) == 1 else None


# --- reading the message ----------------------------------------------------


def read_message_file(value: str, cwd: str) -> tuple[str, str | None]:
    """Read a -F target. Returns (text, reason to block)."""
    if value in ("-", "/dev/stdin") or value.startswith("<") or value.startswith("/dev/fd/"):
        return "", ("the message is piped in, so no check can read it. Write it to a "
                    "file and pass `-F <file>`, or use `-m` for each paragraph")
    if "$" in value or "~" in value:
        return "", (f"the message file path `{value}` is built by the shell, so the "
                    "guard cannot resolve it. Pass a literal path")
    full = value if os.path.isabs(value) else os.path.join(cwd, value)
    real = os.path.realpath(full)
    if real.startswith(FORBIDDEN_ROOTS):
        return "", f"refusing to read a commit message from {real}"
    try:
        info = os.stat(real)
    except OSError:
        return "", (f"the message file {value} does not exist yet. Write it in its own "
                    "command, then commit, so the checks can read it")
    if not stat.S_ISREG(info.st_mode):
        return "", f"{value} is not a regular file, so the message cannot be read safely"
    if info.st_size > MESSAGE_LIMIT:
        return "", (f"the message file is {info.st_size} bytes, over the "
                    f"{MESSAGE_LIMIT} byte limit")
    try:
        with open(real, encoding="utf-8", errors="replace") as fh:
            return fh.read(MESSAGE_LIMIT + 1), None
    except OSError as exc:
        return "", f"cannot read the message file {value}: {exc}"


def reused_message(root: str | None, rev: str) -> str:
    if not root:
        return ""
    return git_out(["-C", root, "log", "-1", "--format=%B", rev]) or ""


class CommitArgs:
    """What `git commit` was asked to use as its message."""

    def __init__(self):
        self.body_parts: list[str] = []
        self.trailers: list[str] = []
        self.pathspecs: list[str] = []
        self.has_body = False
        self.from_file = False
        self.message_files: list[str] = []
        self.no_verify = False
        self.block: str | None = None

    def message(self) -> str:
        parts = list(self.body_parts)
        if self.trailers:
            parts.append("\n".join(self.trailers))
        return "\n\n".join(p.strip("\n") for p in parts if p.strip())


def parse_commit(args: list[str], cwd: str, root: str | None) -> CommitArgs:
    """Parse commit options the way git's parse-options does."""
    result = CommitArgs()
    i = 0

    def apply(option: str, value: str | None) -> None:
        if value is None:
            return
        if option == "--message":
            result.body_parts.append(value)
            result.has_body = True
        elif option == "--file":
            text, why = read_message_file(value, cwd)
            result.from_file = True
            result.message_files.append(value)
            result.has_body = True
            if why and result.block is None:
                result.block = why
            if text:
                result.body_parts.append(text)
        elif option == "--trailer":
            result.trailers.append(value)
        elif option in ("--reuse-message", "--reedit-message"):
            text = reused_message(root, value)
            result.has_body = True
            if text:
                result.body_parts.append(text)

    while i < len(args):
        tok = args[i]
        if tok == "--":
            result.pathspecs.extend(args[i + 1:])
            break
        if tok in NO_VERIFY:
            result.no_verify = True
            i += 1
            continue
        if tok.startswith("--"):
            name, sep, inline = tok.partition("=")
            option = unique_long(name, COMMIT_VALUE_LONG)
            if option:
                if sep:
                    apply(option, inline)
                    i += 1
                else:
                    apply(option, args[i + 1] if i + 1 < len(args) else None)
                    i += 2
                continue
            # An optional-value option takes a value only through `=`.
            if unique_long(name, COMMIT_OPTARG_LONG):
                i += 1
                continue
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1:
            cluster, pos, consumed = tok[1:], 0, False
            while pos < len(cluster):
                ch = cluster[pos]
                if ch in COMMIT_VALUE_SHORT:
                    rest = cluster[pos + 1:]
                    if rest:
                        apply(COMMIT_VALUE_SHORT[ch], rest)
                        i += 1
                    else:
                        apply(COMMIT_VALUE_SHORT[ch], args[i + 1] if i + 1 < len(args) else None)
                        i += 2
                    consumed = True
                    break
                if ch in COMMIT_OPTARG_SHORT:
                    break  # the rest of the cluster is its value, never the next token
                if ch == "n":
                    result.no_verify = True
                pos += 1
            if not consumed:
                i += 1
            continue
        result.pathspecs.append(tok)
        i += 1
    return result


# --- private paths ----------------------------------------------------------

PATHSPEC_MAGIC = re.compile(r"^:(?:\([^)]*\)|[!^/:]*)")


def strip_magic(pathspec: str) -> tuple[str, bool]:
    """Remove git pathspec magic. Returns (path, case insensitive)."""
    icase = "icase" in pathspec[:pathspec.find(")") + 1] if pathspec.startswith(":(") else False
    return PATHSPEC_MAGIC.sub("", pathspec), icase


def touches_private(paths: list[str]) -> list[str]:
    hits = []
    for path in paths:
        candidate, icase = strip_magic(path.strip())
        norm = candidate.replace("\\", "/")
        while norm.startswith("./"):
            norm = norm[2:]
        norm = norm.rstrip("/")
        base = os.path.basename(norm)
        for private in PRIVATE_PATHS:
            names = (base, norm)
            if icase:
                names = tuple(n.lower() for n in names)
                private_cmp = private.lower()
            else:
                private_cmp = private
            if (names[0] == private_cmp or names[1] == private_cmp
                    or names[1].startswith(private_cmp + "/")
                    or f"/{private_cmp}/" in f"/{names[1]}/"):
                hits.append(path)
                break
    return hits


def git_lines(root: str, args: list[str]) -> list[str]:
    out = git_out(["-C", root, *args])
    return out.splitlines() if out else []


def tracked_private(root: str, ref: str | None = None) -> list[str]:
    if ref:
        return touches_private(git_lines(root, ["ls-tree", "-r", "--name-only", ref]))
    return touches_private(git_lines(root, ["ls-files"]))


def staged_private(root: str) -> list[str]:
    return touches_private(git_lines(root, ["diff", "--cached", "--name-only"]))


def unignored_private(root: str, include_ignored: bool = False) -> list[str]:
    """Private paths a broad add would pick up right now."""
    args = ["status", "--porcelain", "--untracked-files=all"]
    if include_ignored:
        args.append("--ignored")
    lines = git_lines(root, args)
    paths = [line[3:].strip().strip('"') for line in lines if len(line) > 3]
    return touches_private(paths)


def pushed_private(root: str, args: list[str]) -> list[str]:
    """Private paths anywhere in the commits this push would send."""
    positional = [a for a in args if not a.startswith("-")]
    remote = positional[0] if positional else "origin"
    refs = [spec.split(":", 1)[0].lstrip("+") for spec in positional[1:]] or ["HEAD"]
    hits: list[str] = []
    for ref in refs:
        if not ref or ref == ".":
            continue
        names = git_out(["-C", root, "log", "--name-only", "--format=", ref,
                         f"--not", f"--remotes={remote}"])
        if names is None:
            names = git_out(["-C", root, "log", "--name-only", "--format=", "-n", "200", ref])
        if names:
            hits.extend(touches_private(names.splitlines()))
        hits.extend(tracked_private(root, ref))
    return hits


BROAD_ADD = {".", "./", "-A", "--all", "-u", "--update", ":/", "*", "..", "$PWD"}


def is_broad(pathspec: str) -> bool:
    if pathspec in BROAD_ADD:
        return True
    # A glob or an unexpanded variable names files the guard cannot enumerate, so
    # the repository state has to be checked instead of the literal text.
    return any(ch in pathspec for ch in "*?[$")


# --- linters ----------------------------------------------------------------


def run_linters(message: str, excerpts: bool) -> str | None:
    """Run both message linters concurrently. Returns findings, or None."""
    here = os.path.dirname(os.path.abspath(__file__))
    jobs = [("lint-prose.py", ["--profile", "commit"]), ("lint-commit.py", [])]
    procs = []
    for script, extra in jobs:
        path = os.path.join(here, script)
        if not os.path.exists(path):
            continue
        argv = [sys.executable, path, "--stdin", "--label", "commit-message", *extra]
        if not excerpts:
            argv.append("--no-excerpt")
        try:
            procs.append((script, subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True)))
        except Exception:
            fail("BLOCKED by taurus git guard: the message linters could not start, so "
                 f"the commit was not checked ({script}).")

    findings = []
    for script, proc in procs:
        try:
            out, _ = proc.communicate(input=message, timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            fail(f"BLOCKED by taurus git guard: {script} timed out on this message, so "
                 "it was not checked. Shorten the message and commit again.")
        except Exception:
            fail(f"BLOCKED by taurus git guard: {script} failed, so the message was not "
                 "checked.")
        if proc.returncode not in (0, 1):
            fail(f"BLOCKED by taurus git guard: {script} exited {proc.returncode}, so the "
                 "message was not checked.")
        if proc.returncode == 1:
            findings.append(out.strip() or f"{script} reported findings")
    return "\n".join(findings) if findings else None


def check_message(message: str, from_file: bool, has_body: bool) -> None:
    for pattern in ATTRIBUTION_PATTERNS:
        if pattern.search(message):
            fail(
                "BLOCKED by taurus git guard: the commit message carries AI attribution "
                f"(matched /{pattern.pattern}/).\n"
                "Rewrite the message with no Claude/Anthropic mention, no Co-Authored-By "
                "trailer, and no robot emoji. Describe the change and why it was made."
            )
    if not has_body:
        # Trailers alone. git opens the editor for the subject, which the guard never
        # sees, so the grammar is checked by the repo-side commit-msg hook.
        return
    if len(message) > MESSAGE_LIMIT:
        fail(f"BLOCKED by taurus git guard: the commit message is {len(message)} bytes, "
             f"over the {MESSAGE_LIMIT} byte limit. Shorten it.")
    findings = run_linters(message, excerpts=not from_file)
    if findings:
        fail(
            "BLOCKED by taurus git guard: the commit message fails the standard.\n"
            + findings +
            "\nFormat: <type>[(scope)][!]: <description>, blank line, body, blank line, "
            "footers.\nSee https://www.conventionalcommits.org/en/v1.0.0/"
        )


# --- the check ---------------------------------------------------------------


def check(payload: dict) -> None:
    tool = payload.get("tool_name") or payload.get("toolName")
    if tool != "Bash":
        return
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = tool_input.get("command") or ""
    if "git" not in command:
        return

    cwd = payload.get("cwd") or os.getcwd()
    default_root = repo_root(cwd)

    construct = hidden_git_write(command)
    if construct:
        fail(
            f"BLOCKED by taurus git guard: this command uses {construct}.\n"
            "Rewrite it as a plain git command. For a multi-paragraph message, write the "
            "message to a file in its own command, then run `git commit -F <file>`."
        )

    for tokens, seg_start, seg_end in segments(command):
        sub, args, inline, retarget, clean = git_subcommand(tokens)
        if not clean:
            fail(
                "BLOCKED by taurus git guard: this git command carries an option the "
                "guard cannot parse, so it cannot tell which subcommand runs.\n"
                "Rewrite it with the options spelled out in full, or split it into "
                "separate commands."
            )
        if sub is None:
            continue

        root = default_root
        if retarget:
            target = retarget if os.path.isabs(retarget) else os.path.join(cwd, retarget)
            root = repo_root(target) or root

        sub, prefix, readable = resolve_alias(root, sub, inline)
        if not readable:
            fail(
                "BLOCKED by taurus git guard: this git subcommand resolves through a "
                "shell alias or an alias chain the guard cannot follow.\n"
                "Run the underlying git command directly."
            )
        args = prefix + args
        exempt = is_source_repo(root)

        if sub == "commit":
            if expanded_in(command, seg_start, seg_end):
                fail(
                    "BLOCKED by taurus git guard: this commit's arguments are built by "
                    "shell expansion, so the guard reads text that is not the message "
                    "git will receive.\n"
                    "Write the message to a file in its own command, then run "
                    "`git commit -F <file>`, or pass one `-m` per paragraph."
                )
            parsed = parse_commit(args, cwd, root)
            if parsed.no_verify:
                fail(
                    "BLOCKED by taurus git guard: `--no-verify` skips the repo's "
                    "commit-msg hook, which is where the message standard is enforced.\n"
                    "Fix the message instead of bypassing the check."
                )
            earlier = without_heredocs(command)[:seg_start]
            if parsed.from_file and REDIRECTION.search(earlier) and any(
                    os.path.basename(p) and os.path.basename(p) in earlier
                    for p in parsed.message_files):
                fail(
                    "BLOCKED by taurus git guard: this command writes the message file "
                    "and commits from it in one line, so the message the guard read is "
                    "not the message git will use.\n"
                    "Write the message file in its own command, then commit."
                )
            if parsed.block:
                fail("BLOCKED by taurus git guard: " + parsed.block + ".")
            message = parsed.message()
            if message.strip():
                check_message(message, parsed.from_file, parsed.has_body)
        elif sub in ("merge", "tag", "revert", "cherry-pick", "notes"):
            message = parse_commit(args, cwd, root).message()
            for pattern in ATTRIBUTION_PATTERNS:
                if message.strip() and pattern.search(message):
                    fail(
                        "BLOCKED by taurus git guard: the message carries AI attribution "
                        f"(matched /{pattern.pattern}/).\n"
                        "Rewrite it with no Claude/Anthropic mention."
                    )

        if exempt:
            continue

        if sub in STAGING_SUBS:
            forced = any(a in ("-f", "--force") or a.startswith("--pathspec-from-file")
                         for a in args)
            explicit = [a for a in args if not a.startswith("-")]
            hits = touches_private(explicit)
            if hits:
                fail(
                    "BLOCKED by taurus git guard: refusing to stage "
                    f"{', '.join(sorted(set(hits)))}.\n"
                    "CLAUDE.md, AGENTS.md, .claude/ and .mcp.json stay local. Add them to "
                    ".gitignore instead."
                )
            for arg in args:
                if arg.startswith("--pathspec-from-file"):
                    _, _, path = arg.partition("=")
                    listed, _ = read_message_file(path, cwd) if path else ("", None)
                    hits = touches_private(listed.splitlines())
                    if hits:
                        fail(
                            "BLOCKED by taurus git guard: the pathspec file lists "
                            f"{', '.join(sorted(set(hits)))}."
                        )
            broad = any(is_broad(a) for a in args) or not explicit
            if broad and root:
                hits = unignored_private(root, include_ignored=forced)
                if hits:
                    fail(
                        "BLOCKED by taurus git guard: a broad `git "
                        f"{sub}` would stage {', '.join(sorted(set(hits)))}.\n"
                        "Add these to .gitignore first (its own commit), then stage the "
                        "real changes with explicit paths."
                    )

        if sub == "commit" and root:
            hits = staged_private(root)
            stages_everything = any(
                a == "--all" or (a.startswith("-") and not a.startswith("--") and "a" in a[1:])
                for a in args
            )
            if not hits and stages_everything:
                hits = unignored_private(root)
            if hits:
                fail(
                    "BLOCKED by taurus git guard: the staged tree contains "
                    f"{', '.join(sorted(set(hits)))}.\n"
                    "Run `git restore --staged <path>` on them, add them to .gitignore, "
                    "then commit."
                )

        if sub == "push" and root:
            hits = pushed_private(root, args)
            if hits:
                fail(
                    "BLOCKED by taurus git guard: the commits being pushed touch "
                    f"{', '.join(sorted(set(hits)))}.\n"
                    "A `git rm -r --cached` plus a commit removes the file from the tip, "
                    "and the blob stays in history. Rewrite the range with git filter-repo "
                    "before pushing."
                )


def main() -> None:
    payload = read_payload()
    try:
        check(payload)
    except SystemExit:
        raise
    except MemoryError:
        fail("BLOCKED by taurus git guard: this command exhausted the guard's memory, so "
             "it was not checked.")
    except Exception as exc:  # a guard bug must never wedge the session
        sys.stderr.write(f"taurus git guard skipped after internal error: {exc}\n")
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
