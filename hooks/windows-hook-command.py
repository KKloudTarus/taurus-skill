#!/usr/bin/env python3
"""Emit a Codex Windows hook command without cmd.exe path quoting."""

import base64
import sys


def windows_command(python: str, guard: str) -> str:
    # Only trusted install paths enter this script. Hook input stays on stdin.
    def literal(value: str) -> str:
        # PowerShell recognizes smart single quotes as delimiters too.
        for quote in "'‘’‚‛":
            value = value.replace(quote, quote * 2)
        return "'" + value + "'"

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$ProgressPreference = 'SilentlyContinue'\n"
        "$utf8 = New-Object System.Text.UTF8Encoding($false)\n"
        "[Console]::InputEncoding = $utf8\n"
        "$OutputEncoding = $utf8\n"
        "$env:PYTHONIOENCODING = 'utf-8'\n"
        f"[Console]::In.ReadToEnd() | & {literal(python)} {literal(guard)}\n"
        "exit $LASTEXITCODE\n"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    # Resolve the Windows system executable, never a project-local or PATH copy.
    powershell = r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
    return powershell + " -NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: windows-hook-command.py PYTHON GUARD")
    print(windows_command(sys.argv[1], sys.argv[2]))
