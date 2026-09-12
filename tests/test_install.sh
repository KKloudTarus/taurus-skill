#!/usr/bin/env bash
# Tests for install.sh against an isolated CLAUDE_CONFIG_DIR. Run: bash tests/test_install.sh
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

setup() {
  WORK="$(mktemp -d)"
  export CLAUDE_CONFIG_DIR="$WORK/.claude"
  export HOME_ORIG="$HOME"
}
teardown() { rm -rf "$WORK"; export HOME="$HOME_ORIG"; }

check() {
  local label="$1"; shift
  if "$@"; then PASS=$((PASS+1)); printf 'ok   %s\n' "$label"
  else FAIL=$((FAIL+1)); printf 'FAIL %s\n' "$label"; fi
}
check_not() {
  local label="$1"; shift
  if "$@"; then FAIL=$((FAIL+1)); printf 'FAIL %s\n' "$label"
  else PASS=$((PASS+1)); printf 'ok   %s\n' "$label"; fi
}
contains() { grep -qF "$2" "$1"; }

# --- install creates the expected tree --------------------------------------
setup
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
check "taurus root is a symlink to the repo"        test "$(readlink "$CLAUDE_CONFIG_DIR/taurus")" = "$REPO"
check "the single skill is linked"                   test -L "$CLAUDE_CONFIG_DIR/skills/taurus"
check "every skill is linked"                       test "$(find "$CLAUDE_CONFIG_DIR/skills" -maxdepth 1 -type l | wc -l)" -eq "$(find "$REPO/skills" -maxdepth 1 -mindepth 1 -type d | wc -l)"
check "agents are linked"                           test -L "$CLAUDE_CONFIG_DIR/agents/qa-verifier.md"
check "commands are linked"                         test -L "$CLAUDE_CONFIG_DIR/commands/deliver.md"
check "skill link resolves to a SKILL.md"           test -f "$CLAUDE_CONFIG_DIR/skills/taurus/SKILL.md"
check "references reachable through the link"       test -f "$CLAUDE_CONFIG_DIR/skills/taurus/references/writing-voice.md"
check "settings.json is valid json"                 python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$CLAUDE_CONFIG_DIR/settings.json"
check "guard hook is wired"                         contains "$CLAUDE_CONFIG_DIR/settings.json" "guard-git.py"
check "hook matcher is Bash"                        python3 -c "
import json,sys
s=json.load(open(sys.argv[1]))
pre=s['hooks']['PreToolUse']
assert any(e['matcher']=='Bash' and any('guard-git.py' in h['command'] for h in e['hooks']) for e in pre)
" "$CLAUDE_CONFIG_DIR/settings.json"
check "rules block written to CLAUDE.md"            contains "$CLAUDE_CONFIG_DIR/CLAUDE.md" "Taurus Delivery Standard"
check "rules block has begin marker"                contains "$CLAUDE_CONFIG_DIR/CLAUDE.md" "taurus:begin"
check "rules block has end marker"                  contains "$CLAUDE_CONFIG_DIR/CLAUDE.md" "taurus:end"

# --- install is idempotent ---------------------------------------------------
before_settings="$(cat "$CLAUDE_CONFIG_DIR/settings.json")"
before_memory="$(cat "$CLAUDE_CONFIG_DIR/CLAUDE.md")"
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
check "settings unchanged after reinstall"          test "$before_settings" = "$(cat "$CLAUDE_CONFIG_DIR/settings.json")"
check "CLAUDE.md unchanged after reinstall"         test "$before_memory" = "$(cat "$CLAUDE_CONFIG_DIR/CLAUDE.md")"
check "hook wired exactly once"                     test "$(grep -o 'guard-git.py' "$CLAUDE_CONFIG_DIR/settings.json" | wc -l)" -eq 1

# --- uninstall removes what install added ------------------------------------
bash "$REPO/install.sh" --uninstall >/dev/null 2>&1
check_not "skill links removed"                     test -L "$CLAUDE_CONFIG_DIR/skills/taurus"
check_not "agent links removed"                     test -L "$CLAUDE_CONFIG_DIR/agents/qa-verifier.md"
check_not "command links removed"                   test -L "$CLAUDE_CONFIG_DIR/commands/deliver.md"
check_not "taurus root removed"                     test -L "$CLAUDE_CONFIG_DIR/taurus"
check_not "hook unwired"                            contains "$CLAUDE_CONFIG_DIR/settings.json" "guard-git.py"
check_not "rules block removed"                     contains "$CLAUDE_CONFIG_DIR/CLAUDE.md" "taurus:begin"
check "settings still valid json after uninstall"   python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$CLAUDE_CONFIG_DIR/settings.json"
teardown

# --- existing user config is preserved ---------------------------------------
setup
mkdir -p "$CLAUDE_CONFIG_DIR"
cat > "$CLAUDE_CONFIG_DIR/settings.json" <<'JSON'
{
  "theme": "dark",
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "/usr/local/bin/other-hook"}]}
    ],
    "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "notify"}]}]
  }
}
JSON
printf '# My notes\n\nKeep this line.\n' > "$CLAUDE_CONFIG_DIR/CLAUDE.md"
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
check "existing setting preserved"                  python3 -c "
import json,sys; assert json.load(open(sys.argv[1]))['theme']=='dark'" "$CLAUDE_CONFIG_DIR/settings.json"
check "existing Bash hook preserved"                contains "$CLAUDE_CONFIG_DIR/settings.json" "other-hook"
check "existing Stop hook preserved"                contains "$CLAUDE_CONFIG_DIR/settings.json" "notify"
check "guard added to the same Bash matcher"        python3 -c "
import json,sys
pre=json.load(open(sys.argv[1]))['hooks']['PreToolUse']
bash=[e for e in pre if e['matcher']=='Bash']
assert len(bash)==1, bash
assert len(bash[0]['hooks'])==2, bash
" "$CLAUDE_CONFIG_DIR/settings.json"
check "existing CLAUDE.md content preserved"        contains "$CLAUDE_CONFIG_DIR/CLAUDE.md" "Keep this line."
bash "$REPO/install.sh" --uninstall >/dev/null 2>&1
check "other hook survives uninstall"               contains "$CLAUDE_CONFIG_DIR/settings.json" "other-hook"
check "user notes survive uninstall"                contains "$CLAUDE_CONFIG_DIR/CLAUDE.md" "Keep this line."
teardown

# --- stale links from a renamed or consolidated source ----------------------
setup
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
ln -sfn "$REPO/skills/removed-skill" "$CLAUDE_CONFIG_DIR/skills/removed-skill"
ln -sfn "$REPO/agents/removed-agent.md" "$CLAUDE_CONFIG_DIR/agents/removed-agent.md"
ln -sfn "/somewhere/else/keep-me" "$CLAUDE_CONFIG_DIR/skills/keep-me"
check "stale link exists before reinstall"          test -L "$CLAUDE_CONFIG_DIR/skills/removed-skill"
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
check_not "stale skill link pruned"                 test -L "$CLAUDE_CONFIG_DIR/skills/removed-skill"
check_not "stale agent link pruned"                 test -L "$CLAUDE_CONFIG_DIR/agents/removed-agent.md"
check "foreign broken link left alone"              test -L "$CLAUDE_CONFIG_DIR/skills/keep-me"
check "live links survive the prune"                test -f "$CLAUDE_CONFIG_DIR/skills/taurus/SKILL.md"
teardown

# --- safety --------------------------------------------------------------
setup
mkdir -p "$CLAUDE_CONFIG_DIR/skills/taurus"
echo "mine" > "$CLAUDE_CONFIG_DIR/skills/taurus/SKILL.md"
bash "$REPO/install.sh" --no-gitignore --no-githooks >/dev/null 2>&1
check "real directory is not clobbered"             contains "$CLAUDE_CONFIG_DIR/skills/taurus/SKILL.md" "mine"
teardown

setup
out="$(bash "$REPO/install.sh" --dry-run --no-gitignore --no-githooks 2>&1)"
check_not "dry run creates nothing"                 test -d "$CLAUDE_CONFIG_DIR"
check "dry run reports actions"                     grep -q "would:" <<<"$out"
check "dry run reports no changes"                  grep -q "Dry run complete. No changes were made." <<<"$out"
check_not "dry run does not claim installation"     grep -q "^Installed\." <<<"$out"
teardown

setup
fake="$(mktemp -d)"
cp "$REPO/install.sh" "$fake/"
out="$(cd "$fake" && bash "$fake/install.sh" --no-gitignore --no-githooks 2>&1)"; rc=$?
check "refuses to install from a non-source dir"    test "$rc" -ne 0
check "refusal explains why"                        grep -q "not the taurus-skill repo" <<<"$out"
rm -rf "$fake"
teardown

# --- global Git hooks are opt-in and legacy installs migrate safely ---------
setup
mkdir -p "$WORK/home"
HOME="$WORK/home" bash "$REPO/install.sh" --no-gitignore >/dev/null 2>&1
check_not "default install leaves core.hooksPath unset" \
  env HOME="$WORK/home" git config --global --get core.hooksPath
HOME="$WORK/home" bash "$REPO/install.sh" --githooks --no-gitignore >/dev/null 2>&1
check "githooks flag sets the managed path" test \
  "$(HOME="$WORK/home" git config --global --get core.hooksPath)" = "$CLAUDE_CONFIG_DIR/taurus/githooks"
HOME="$WORK/home" bash "$REPO/install.sh" --no-gitignore >/dev/null 2>&1
check_not "default reinstall removes the legacy managed path" \
  env HOME="$WORK/home" git config --global --get core.hooksPath
teardown

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
