#!/usr/bin/env bash
# Install the Taurus delivery standard into Claude Code, Codex, or both.
#
# Symlinks the repo so a `git pull` updates every project. Merges hook wiring
# and the always-on rules idempotently. Never overwrites a real file, and never
# writes Codex config.toml.
#
#   ./install.sh                 install or update Claude Code
#   ./install.sh --target codex  install or update Codex
#   ./install.sh --target all    install both
#   ./install.sh --dry-run       print what would change
#   ./install.sh --uninstall     remove everything this script created
#   ./install.sh --githooks      opt in to the global core.hooksPath
#   ./install.sh --no-gitignore  skip the global gitignore entries
#   ./install.sh --no-githooks   compatibility alias for the safe default
#
# CLAUDE_CONFIG_DIR overrides the Claude directory (used by the test suite).
# CODEX_HOME overrides the Codex directory. The default target is claude.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
BEGIN="<!-- taurus:begin - managed by taurus-skill install.sh, edits are overwritten -->"
END="<!-- taurus:end -->"

DRY_RUN=0
UNINSTALL=0
DO_GITIGNORE=1
DO_GITHOOKS=0
TARGET="claude"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --githooks) DO_GITHOOKS=1; shift ;;
    --no-gitignore) DO_GITIGNORE=0; shift ;;
    --no-githooks) DO_GITHOOKS=0; shift ;;
    --target)
      [ $# -ge 2 ] || { echo "missing value for --target" >&2; exit 2; }
      TARGET="$2"; shift 2 ;;
    --target=*) TARGET="${1#--target=}"; shift ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

case "$TARGET" in
  claude|codex|all) ;;
  *) echo "unknown target: $TARGET (expected claude, codex, or all)" >&2; exit 2 ;;
esac

say()  { printf '%s\n' "$*"; }
run()  { if [ "$DRY_RUN" = 1 ]; then say "  would: $*"; else "$@"; fi; }

want() {
  case "$TARGET" in
    all) return 0 ;;
    "$1") return 0 ;;
    *) return 1 ;;
  esac
}

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
      "$src"/*|"$src") run rm -f "$entry"; say "  unlink $entry" ;;
    esac
  done
}

assert_link_root() {
  local path="$1"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    echo "refusing to overwrite $path (exists and is not a symlink)" >&2
    exit 1
  fi
}

link_root() {
  local root="$1"
  run mkdir -p "$(dirname "$root")"
  run ln -sfn "$REPO" "$root"
  say "  link $root -> $REPO"
  if [ "$DRY_RUN" = 0 ] && [ ! -L "$root" ]; then
    say "  warning: $root is not a symlink, so git pull will not update this install"
  fi
}

# --- managed instruction block ----------------------------------------------

write_marked_block() {
  local memory="$1"
  shift
  if [ "$DRY_RUN" = 1 ]; then say "  would: write managed block into $memory"; return 0; fi
  python3 - "$memory" "$BEGIN" "$END" "$@" <<'PY'
import os, sys
memory, begin, end, *rule_paths = sys.argv[1:]
rules = "\n\n".join(open(path, encoding="utf-8").read().strip() for path in rule_paths)
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
  say "  wrote managed rules block into $memory"
}

remove_marked_block() {
  local memory="$1"
  [ -f "$memory" ] || return 0
  if [ "$DRY_RUN" = 1 ]; then say "  would: remove managed block from $memory"; return 0; fi
  python3 - "$memory" "$BEGIN" "$END" <<'PY'
import sys
memory, begin, end = sys.argv[1:4]
text = open(memory, encoding="utf-8").read()
if begin in text and end in text:
    text = text.split(begin)[0].rstrip() + "\n" + text.split(end, 1)[1].lstrip()
    open(memory, "w", encoding="utf-8").write(text.lstrip("\n"))
PY
  say "  removed managed rules block from $memory"
}

# --- Claude settings.json hook wiring ---------------------------------------

write_settings() {
  local mode="$1" settings="$2" guard="$3"
  if [ "$DRY_RUN" = 1 ]; then say "  would: $mode hook wiring in $settings"; return 0; fi
  python3 - "$settings" "$guard" "$mode" <<'PY'
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
  say "  ${mode}ed hook wiring in $settings"
}

# --- Codex hooks.json -------------------------------------------------------

write_codex_hooks() {
  local mode="$1" path="$2" guard="$3"
  if [ "$DRY_RUN" = 1 ]; then say "  would: $mode hook wiring in $path"; return 0; fi
  python3 - "$path" "$guard" "$mode" <<'PY'
import json, os, sys
path, guard, mode = sys.argv[1], sys.argv[2], sys.argv[3]
existed = os.path.exists(path)
if mode != "install" and not existed:
    sys.exit(0)
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
except (OSError, json.JSONDecodeError):
    doc = {}
if not isinstance(doc, dict):
    doc = {}

command = f"python3 {guard}"
hooks = doc.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])
if not isinstance(pre, list):
    pre = []

def strip_guard(entries):
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        inner = entry.get("hooks", [])
        if not isinstance(inner, list):
            kept.append(entry)
            continue
        filtered = [h for h in inner if not (isinstance(h, dict) and "guard-git.py" in str(h.get("command", "")))]
        if filtered:
            entry = {**entry, "hooks": filtered}
            kept.append(entry)
        elif not inner:
            kept.append(entry)
    return kept

pre = strip_guard(pre)
matcher = "^(Bash|shell)$"
if mode == "install":
    handler = {
        "type": "command",
        "command": command,
        "timeout": 30,
        "statusMessage": "Checking git command",
    }
    for entry in pre:
        if isinstance(entry, dict) and entry.get("matcher") == matcher:
            entry.setdefault("hooks", []).append(handler)
            break
    else:
        pre.append({"matcher": matcher, "hooks": [handler]})

hooks["PreToolUse"] = pre
if not pre:
    hooks.pop("PreToolUse", None)
if not hooks:
    doc.pop("hooks", None)

with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  say "  ${mode}ed hook wiring in $path"
}

# --- global git hooks -------------------------------------------------------

write_hookspath() {
  # The PreToolUse guard reads a command string that bash and git each parse by
  # their own rules, so it can only ever be the fast layer. These hooks see what git
  # actually assembled, and are the control of record.
  # A path whose realpath is this repo's githooks/ is already managed. Do not
  # retarget it: Claude and Codex installs share one pack.
  local dest="$1" current current_real ours
  ours="$(cd "$REPO/githooks" && pwd -P)"
  current="$(git config --global --get core.hooksPath || true)"
  if [ -n "$current" ]; then
    if [ -d "$current" ]; then
      current_real="$(cd "$current" && pwd -P)"
    else
      current_real=""
    fi
    if [ "$current_real" = "$ours" ]; then
      if [ "$current" = "$dest" ]; then
        say "  core.hooksPath already $current"
      else
        say "  core.hooksPath already points at this pack ($current)"
      fi
      return 0
    fi
    say "  skip core.hooksPath (already set to $current)"
    say "        to opt in:  git config --global core.hooksPath $dest"
    return 0
  fi
  if [ "$DRY_RUN" = 1 ]; then say "  would: set core.hooksPath to $dest"; return 0; fi
  git config --global core.hooksPath "$dest"
  say "  core.hooksPath -> $dest (commit-msg, pre-commit, pre-push)"
}

remove_hookspath() {
  local dest="$1" current
  current="$(git config --global --get core.hooksPath || true)"
  [ "$current" = "$dest" ] || return 0
  if [ "$DRY_RUN" = 1 ]; then say "  would: unset core.hooksPath"; return 0; fi
  git config --global --unset core.hooksPath
  say "  unset core.hooksPath"
}

# --- global gitignore -------------------------------------------------------

gitignore_file() {
  local file
  file="$(git config --global --get core.excludesFile || true)"
  if [ -z "$file" ]; then
    file="${XDG_CONFIG_HOME:-$HOME/.config}/git/ignore"
    run mkdir -p "$(dirname "$file")"
    run git config --global core.excludesFile "$file"
  fi
  file="${file/#\~/$HOME}"
  printf '%s\n' "$file"
}

write_gitignore() {
  # One list for both targets. .codex/ is the Codex counterpart of .claude/.
  local file entry
  local label=".claude/, CLAUDE.md, AGENTS.md, .mcp.json, .codex/"
  file="$(gitignore_file)"
  if [ "$DRY_RUN" = 1 ]; then say "  would: add agent-config entries to $file"; return 0; fi
  touch "$file"
  for entry in ".claude/" "CLAUDE.md" "AGENTS.md" ".mcp.json" ".codex/"; do
    grep -qxF "$entry" "$file" || printf '%s\n' "$entry" >> "$file"
  done
  say "  global gitignore covers $label ($file)"
}

# --- targets ----------------------------------------------------------------

install_claude() {
  local root="$CLAUDE_DIR/taurus"
  link_root "$root"
  link_into "$REPO/skills"   "$CLAUDE_DIR/skills"   '*'
  link_into "$REPO/agents"   "$CLAUDE_DIR/agents"   '*.md'
  link_into "$REPO/commands" "$CLAUDE_DIR/commands" '*.md'
  write_settings install "$CLAUDE_DIR/settings.json" "$root/hooks/guard-git.py"
  write_marked_block "$CLAUDE_DIR/CLAUDE.md" "$REPO/rules/always-on.md"
}

install_codex() {
  local root="$CODEX_DIR/taurus" override="$CODEX_DIR/AGENTS.override.md"
  link_root "$root"
  link_into "$REPO/skills" "$HOME/.agents/skills" '*'
  link_into "$REPO/compat/codex/skills" "$HOME/.agents/skills" '*'
  link_into "$REPO/compat/codex/agents" "$CODEX_DIR/agents" '*.toml'
  write_codex_hooks install "$CODEX_DIR/hooks.json" "$root/hooks/guard-git.py"
  write_marked_block "$CODEX_DIR/AGENTS.md" "$REPO/rules/always-on.md" "$REPO/rules/codex-delta.md"
  if [ -s "$override" ]; then
    say "  warning: $override is non-empty, so Codex ignores AGENTS.md"
  fi
}

uninstall_claude() {
  local root="$CLAUDE_DIR/taurus"
  say "Removing the Taurus delivery standard from $CLAUDE_DIR"
  unlink_from "$CLAUDE_DIR/skills" "$REPO/skills"
  unlink_from "$CLAUDE_DIR/agents" "$REPO/agents"
  unlink_from "$CLAUDE_DIR/commands" "$REPO/commands"
  [ -L "$root" ] && { run rm -f "$root"; say "  unlink $root"; }
  write_settings uninstall "$CLAUDE_DIR/settings.json" "$root/hooks/guard-git.py"
  remove_hookspath "$root/githooks"
  remove_marked_block "$CLAUDE_DIR/CLAUDE.md"
}

uninstall_codex() {
  local root="$CODEX_DIR/taurus"
  say "Removing the Taurus delivery standard from $CODEX_DIR"
  unlink_from "$HOME/.agents/skills" "$REPO/skills"
  unlink_from "$HOME/.agents/skills" "$REPO/compat/codex/skills"
  unlink_from "$CODEX_DIR/agents" "$REPO/compat/codex/agents"
  [ -L "$root" ] && { run rm -f "$root"; say "  unlink $root"; }
  write_codex_hooks uninstall "$CODEX_DIR/hooks.json" "$root/hooks/guard-git.py"
  remove_hookspath "$root/githooks"
  remove_marked_block "$CODEX_DIR/AGENTS.md"
}

apply_githooks() {
  if [ "$DO_GITHOOKS" = 1 ]; then
    if want claude; then
      write_hookspath "$CLAUDE_DIR/taurus/githooks"
    else
      write_hookspath "$CODEX_DIR/taurus/githooks"
    fi
    return 0
  fi
  # Migrate installations from versions that enabled the global path by default.
  # Only the exact path managed by this installer is removed.
  # Use if, not &&: a bare `want codex && ...` is the function's last command, and
  # its non-zero status would abort the script under set -e.
  if want claude; then
    remove_hookspath "$CLAUDE_DIR/taurus/githooks"
  fi
  if want codex; then
    remove_hookspath "$CODEX_DIR/taurus/githooks"
  fi
}

finish() {
  say ""
  if [ "$DRY_RUN" = 1 ]; then
    say "Dry run complete. No changes were made."
  else
    if want claude; then
      say "Installed. Start a new Claude Code session to pick it up."
      say "Commands: /deliver  /verify  /panel  /ship  /style"
    fi
    if want codex; then
      say "Installed. Start a new Codex session to pick it up."
      say "Skills: \$taurus-deliver  \$taurus-verify  \$taurus-panel  \$taurus-ship  \$taurus-style"
      say "Codex hook: it does nothing until you trust it in /hooks."
    fi
  fi
  say "Update:   git -C $REPO pull"
}

# --- main -------------------------------------------------------------------

if [ "$UNINSTALL" = 1 ]; then
  want claude && uninstall_claude
  want codex && uninstall_codex
  say "Done. The global gitignore entries were left in place."
  exit 0
fi

say "Installing the Taurus delivery standard"
say "  source: $REPO"
want claude && say "  claude: $CLAUDE_DIR"
want codex && say "  codex:  $CODEX_DIR"

if [ ! -f "$REPO/.taurus-skill-source" ]; then
  echo "refusing to install: $REPO is not the taurus-skill repo" >&2
  exit 1
fi

want claude && assert_link_root "$CLAUDE_DIR/taurus"
want codex && assert_link_root "$CODEX_DIR/taurus"

want claude && install_claude
want codex && install_codex
apply_githooks
if [ "$DO_GITIGNORE" = 1 ]; then
  write_gitignore
fi
finish
