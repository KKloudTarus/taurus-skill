#!/usr/bin/env bash
# Install the Taurus delivery standard into the user's global Claude Code config.
#
# Symlinks skills, agents, and commands into ~/.claude so a `git pull` in this repo
# updates every project on the machine. Merges the hook wiring into settings.json
# and the always-on rules into ~/.claude/CLAUDE.md, both idempotently.
#
#   ./install.sh                 install or update
#   ./install.sh --dry-run       print what would change
#   ./install.sh --uninstall     remove everything this script created
#   ./install.sh --no-gitignore  skip the global gitignore entries
#   ./install.sh --no-githooks   skip the global core.hooksPath
#
# CLAUDE_CONFIG_DIR overrides the target directory (used by the test suite).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SETTINGS="$CLAUDE_DIR/settings.json"
USER_MEMORY="$CLAUDE_DIR/CLAUDE.md"
LINK_ROOT="$CLAUDE_DIR/taurus"
BEGIN="<!-- taurus:begin - managed by taurus-skill install.sh, edits are overwritten -->"
END="<!-- taurus:end -->"

DRY_RUN=0
UNINSTALL=0
DO_GITIGNORE=1
DO_GITHOOKS=1

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --no-gitignore) DO_GITIGNORE=0 ;;
    --no-githooks) DO_GITHOOKS=0 ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
run()  { if [ "$DRY_RUN" = 1 ]; then say "  would: $*"; else "$@"; fi; }

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 1; }
}
require python3
require git

# --- link helpers -----------------------------------------------------------

prune_stale() {
  # prune_stale <target dir> <source dir>: drop symlinks into source that no longer
  # resolve. Renaming or consolidating anything in the repo leaves these behind.
  local dst="$1" src="$2" entry
  [ -d "$dst" ] || return 0
  for entry in "$dst"/*; do
    [ -L "$entry" ] || continue
    [ -e "$entry" ] && continue
    case "$(readlink "$entry")" in
      "$src"/*) run rm -f "$entry"; say "  prune $entry (stale)" ;;
    esac
  done
}

link_into() {
  # link_into <source dir> <target dir> <glob>
  local src="$1" dst="$2" glob="$3" entry name target
  [ -d "$src" ] || return 0
  run mkdir -p "$dst"
  prune_stale "$dst" "$src"
  shopt -s nullglob
  for entry in "$src"/$glob; do
    name="$(basename "$entry")"
    target="$dst/$name"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
      say "  skip $target (exists and is not a symlink)"
      continue
    fi
    run ln -sfn "$entry" "$target"
    say "  link $target"
  done
  shopt -u nullglob
}

unlink_from() {
  # unlink_from <target dir> <source dir>: remove symlinks pointing into source
  local dst="$1" src="$2" entry
  [ -d "$dst" ] || return 0
  for entry in "$dst"/*; do
    [ -L "$entry" ] || continue
    case "$(readlink "$entry")" in
      "$src"/*) run rm -f "$entry"; say "  unlink $entry" ;;
    esac
  done
}

# --- managed block in CLAUDE.md --------------------------------------------

write_memory_block() {
  if [ "$DRY_RUN" = 1 ]; then say "  would: write managed block into $USER_MEMORY"; return 0; fi
  python3 - "$USER_MEMORY" "$REPO/rules/always-on.md" "$BEGIN" "$END" <<'PY'
import os, sys
memory, rules_path, begin, end = sys.argv[1:5]
rules = open(rules_path, encoding="utf-8").read().strip()
block = f"{begin}\n\n{rules}\n\n{end}\n"
os.makedirs(os.path.dirname(memory), exist_ok=True)
existing = open(memory, encoding="utf-8").read() if os.path.exists(memory) else ""
if begin in existing and end in existing:
    head = existing.split(begin)[0]
    tail = existing.split(end, 1)[1]
    updated = head + block + tail
else:
    updated = (existing.rstrip() + "\n\n" if existing.strip() else "") + block
open(memory, "w", encoding="utf-8").write(updated)
PY
  say "  wrote managed rules block into $USER_MEMORY"
}

remove_memory_block() {
  [ -f "$USER_MEMORY" ] || return 0
  if [ "$DRY_RUN" = 1 ]; then say "  would: remove managed block from $USER_MEMORY"; return 0; fi
  python3 - "$USER_MEMORY" "$BEGIN" "$END" <<'PY'
import sys
memory, begin, end = sys.argv[1:4]
text = open(memory, encoding="utf-8").read()
if begin in text and end in text:
    text = text.split(begin)[0].rstrip() + "\n" + text.split(end, 1)[1].lstrip()
    open(memory, "w", encoding="utf-8").write(text.lstrip("\n"))
PY
  say "  removed managed rules block from $USER_MEMORY"
}

# --- settings.json hook wiring ---------------------------------------------

write_settings() {
  local mode="$1"
  if [ "$DRY_RUN" = 1 ]; then say "  would: $mode hook wiring in $SETTINGS"; return 0; fi
  python3 - "$SETTINGS" "$LINK_ROOT/hooks/guard-git.py" "$mode" <<'PY'
import json, os, sys
path, guard, mode = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path, encoding="utf-8") as fh:
        settings = json.load(fh)
except (OSError, json.JSONDecodeError):
    settings = {}
if not isinstance(settings, dict):
    settings = {}

command = f"python3 {guard}"
hooks = settings.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])

def strip_guard(entries):
    kept = []
    for entry in entries:
        inner = [h for h in entry.get("hooks", []) if "guard-git.py" not in str(h.get("command", ""))]
        if inner:
            entry = {**entry, "hooks": inner}
            kept.append(entry)
        elif not entry.get("hooks"):
            kept.append(entry)
    return kept

pre = strip_guard(pre)
if mode == "install":
    for entry in pre:
        if entry.get("matcher") == "Bash":
            entry.setdefault("hooks", []).append({"type": "command", "command": command})
            break
    else:
        pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": command}]})

hooks["PreToolUse"] = pre
if not pre:
    hooks.pop("PreToolUse", None)
if not hooks:
    settings.pop("hooks", None)

with open(path, "w", encoding="utf-8") as fh:
    json.dump(settings, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  say "  ${mode}ed hook wiring in $SETTINGS"
}

# --- global git hooks -------------------------------------------------------

write_hookspath() {
  # The PreToolUse guard reads a command string that bash and git each parse by
  # their own rules, so it can only ever be the fast layer. These hooks see what git
  # actually assembled, and are the control of record.
  local current
  current="$(git config --global --get core.hooksPath || true)"
  if [ -n "$current" ] && [ "$current" != "$LINK_ROOT/githooks" ]; then
    say "  skip core.hooksPath (already set to $current)"
    say "        to opt in:  git config --global core.hooksPath $LINK_ROOT/githooks"
    return 0
  fi
  if [ "$DRY_RUN" = 1 ]; then say "  would: set core.hooksPath to $LINK_ROOT/githooks"; return 0; fi
  git config --global core.hooksPath "$LINK_ROOT/githooks"
  say "  core.hooksPath -> $LINK_ROOT/githooks (commit-msg, pre-commit, pre-push)"
}

remove_hookspath() {
  local current
  current="$(git config --global --get core.hooksPath || true)"
  [ "$current" = "$LINK_ROOT/githooks" ] || return 0
  if [ "$DRY_RUN" = 1 ]; then say "  would: unset core.hooksPath"; return 0; fi
  git config --global --unset core.hooksPath
  say "  unset core.hooksPath"
}

# --- global gitignore -------------------------------------------------------

write_gitignore() {
  local file
  file="$(git config --global --get core.excludesFile || true)"
  if [ -z "$file" ]; then
    file="${XDG_CONFIG_HOME:-$HOME/.config}/git/ignore"
    run mkdir -p "$(dirname "$file")"
    run git config --global core.excludesFile "$file"
  fi
  file="${file/#\~/$HOME}"
  if [ "$DRY_RUN" = 1 ]; then say "  would: add agent-config entries to $file"; return 0; fi
  touch "$file"
  local entry
  for entry in ".claude/" "CLAUDE.md" "AGENTS.md" ".mcp.json"; do
    grep -qxF "$entry" "$file" || printf '%s\n' "$entry" >> "$file"
  done
  say "  global gitignore covers .claude/, CLAUDE.md, AGENTS.md, .mcp.json ($file)"
}

# --- main -------------------------------------------------------------------

if [ "$UNINSTALL" = 1 ]; then
  say "Removing the Taurus delivery standard from $CLAUDE_DIR"
  unlink_from "$CLAUDE_DIR/skills" "$REPO/skills"
  unlink_from "$CLAUDE_DIR/agents" "$REPO/agents"
  unlink_from "$CLAUDE_DIR/commands" "$REPO/commands"
  [ -L "$LINK_ROOT" ] && { run rm -f "$LINK_ROOT"; say "  unlink $LINK_ROOT"; }
  write_settings uninstall
  remove_hookspath
  remove_memory_block
  say "Done. The global gitignore entries were left in place."
  exit 0
fi

say "Installing the Taurus delivery standard"
say "  source: $REPO"
say "  target: $CLAUDE_DIR"

if [ ! -f "$REPO/.taurus-skill-source" ]; then
  echo "refusing to install: $REPO is not the taurus-skill repo" >&2
  exit 1
fi

run mkdir -p "$CLAUDE_DIR"
if [ -e "$LINK_ROOT" ] && [ ! -L "$LINK_ROOT" ]; then
  echo "refusing to overwrite $LINK_ROOT (exists and is not a symlink)" >&2
  exit 1
fi
run ln -sfn "$REPO" "$LINK_ROOT"
say "  link $LINK_ROOT -> $REPO"

link_into "$REPO/skills"   "$CLAUDE_DIR/skills"   '*'
link_into "$REPO/agents"   "$CLAUDE_DIR/agents"   '*.md'
link_into "$REPO/commands" "$CLAUDE_DIR/commands" '*.md'

write_settings install
write_memory_block
[ "$DO_GITHOOKS" = 1 ] && write_hookspath
[ "$DO_GITIGNORE" = 1 ] && write_gitignore

say ""
say "Installed. Start a new Claude Code session to pick it up."
say "Commands: /deliver  /verify  /panel  /ship  /style"
say "Update:   git -C $REPO pull"
