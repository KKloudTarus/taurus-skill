"""A small bash lexer, enough to tell code from data in a command string.

hooks/guard-git.py has to decide whether a command runs git, and whether a shell
construct hides that from it. Doing that with regexes over the raw string produced
both false blocks (the word `eval` inside a commit message) and real bypasses (a
`$(...)` sitting between two apostrophes inside a double-quoted string). Both come
from the same mistake: guessing at quoting state instead of tracking it.

This module walks the string once and labels every character:

    n  normal, the shell will interpret it
    s  inside a single-quoted span, literal
    d  inside a double-quoted span, expansions still apply
    h  inside a heredoc body, data

It also reports whether a heredoc delimiter could not be determined or its
terminator never arrived, which the guard treats as unreadable rather than
ignorable.
"""

import re

NORMAL, SINGLE, DOUBLE, HEREDOC = "n", "s", "d", "h"

WORD = re.compile(r"[A-Za-z0-9_]")


class Scan:
    __slots__ = ("text", "mask", "unterminated_heredoc", "unreadable_heredoc")

    def __init__(self, text, mask, unterminated, unreadable):
        self.text = text
        self.mask = mask
        self.unterminated_heredoc = unterminated
        self.unreadable_heredoc = unreadable

    def state(self, index: int) -> str:
        return self.mask[index] if 0 <= index < len(self.mask) else NORMAL

    def is_code(self, start: int, end: int) -> bool:
        """True when every character in [start, end) is shell code, not data."""
        return all(self.mask[i] == NORMAL for i in range(start, min(end, len(self.mask))))

    def expands(self, start: int, end: int) -> bool:
        """True when the span sits where the shell performs expansion."""
        return all(self.mask[i] in (NORMAL, DOUBLE) for i in range(start, min(end, len(self.mask))))


def _read_delimiter(text: str, i: int) -> tuple[str | None, int]:
    """Read a heredoc delimiter, following bash's concatenation rule.

    `<<"EO"F` and `<<EO'F'` both delimit on EOF. An empty delimiter is unreadable.
    """
    while i < len(text) and text[i] in " \t":
        i += 1
    parts = []
    while i < len(text):
        ch = text[i]
        if ch in "'\"":
            close = text.find(ch, i + 1)
            if close < 0:
                return None, i
            parts.append(text[i + 1:close])
            i = close + 1
            continue
        if WORD.match(ch) or ch in "-.":
            parts.append(ch)
            i += 1
            continue
        break
    delimiter = "".join(parts)
    return (delimiter or None), i


def scan(command: str) -> Scan:
    text = command
    mask = [NORMAL] * len(text)
    unterminated = False
    unreadable = False

    i = 0
    single = double = False
    pending: list[tuple[str, bool]] = []  # (delimiter, strip tabs)

    while i < len(text):
        ch = text[i]

        if ch == "\\" and not single:
            mask[i] = SINGLE if single else (DOUBLE if double else NORMAL)
            if i + 1 < len(text):
                mask[i + 1] = mask[i]
            i += 2
            continue

        if ch == "'" and not double:
            single = not single
            mask[i] = SINGLE
            i += 1
            continue

        if ch == '"' and not single:
            double = not double
            mask[i] = DOUBLE
            i += 1
            continue

        state = SINGLE if single else (DOUBLE if double else NORMAL)
        mask[i] = state

        # A heredoc operator only counts where the shell reads operators.
        if state == NORMAL and ch == "<" and text[i:i + 2] == "<<" and text[i:i + 3] != "<<<":
            j = i + 2
            strip = False
            if j < len(text) and text[j] == "-":
                strip = True
                j += 1
            delimiter, j = _read_delimiter(text, j)
            for k in range(i, min(j, len(text))):
                mask[k] = NORMAL
            if delimiter is None:
                unreadable = True
            else:
                pending.append((delimiter, strip))
            i = j
            continue

        if ch == "\n" and state == NORMAL and pending:
            i += 1
            for delimiter, strip in pending:
                start = i
                closed = False
                while i < len(text):
                    end = text.find("\n", i)
                    if end < 0:
                        end = len(text)
                    line = text[i:end]
                    candidate = line.lstrip("\t") if strip else line
                    if candidate == delimiter:
                        closed = True
                        for k in range(start, min(end + 1, len(text))):
                            mask[k] = HEREDOC
                        i = min(end + 1, len(text))
                        break
                    i = end + 1 if end < len(text) else len(text)
                if not closed:
                    unterminated = True
                    for k in range(start, len(text)):
                        mask[k] = HEREDOC
            pending = []
            continue

        i += 1

    if pending:
        unterminated = True

    return Scan(text, mask, unterminated, unreadable)


def substitutions(sc: Scan) -> list[tuple[int, int]]:
    """Spans of $( ... ) and ` ... ` the shell will actually expand."""
    text, out, i = sc.text, [], 0
    while i < len(text):
        if text.startswith("$(", i) and sc.expands(i, i + 2) and sc.state(i) != SINGLE:
            depth, j = 1, i + 2
            while j < len(text) and depth:
                if text[j] == "(" and sc.state(j) != SINGLE:
                    depth += 1
                elif text[j] == ")" and sc.state(j) != SINGLE:
                    depth -= 1
                j += 1
            out.append((i + 2, j - 1 if depth == 0 else len(text)))
            i = j
            continue
        if text[i] == "`" and sc.expands(i, i + 1) and sc.state(i) != SINGLE:
            j = text.find("`", i + 1)
            out.append((i + 1, j if j > 0 else len(text)))
            i = (j + 1) if j > 0 else len(text)
            continue
        i += 1
    return out


PARAMETER = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*|\$[0-9@*#?$!-]")


def parameter_expansions(sc: Scan) -> list[tuple[int, int]]:
    """Spans of $NAME and ${...} the shell will substitute.

    Command substitution is not the only way a command's text changes before git
    sees it. A variable holding a commit message or a pathspec does the same.
    """
    out = []
    for hit in PARAMETER.finditer(sc.text):
        start, end = hit.span()
        if sc.text.startswith("$'", start):
            continue  # ANSI-C quoting, reported separately
        if sc.expands(start, start + 1) and sc.state(start) != SINGLE:
            out.append((start, end))
    return out


def ansi_c_quotes(sc: Scan) -> bool:
    """$'...' is expanded by bash and taken literally by shlex."""
    text = sc.text
    return any(text.startswith("$'", i) and sc.state(i) == NORMAL
               for i in range(len(text) - 1))


def code_spans(sc: Scan) -> list[tuple[int, int]]:
    """Maximal runs of characters the shell interprets as code."""
    out, start = [], None
    for i, state in enumerate(sc.mask):
        if state == NORMAL:
            if start is None:
                start = i
        elif start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(sc.mask)))
    return out
