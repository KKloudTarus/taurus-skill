#!/usr/bin/env bash
# Run every test in the pack. Exit non-zero on the first failing suite.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FAILED=()
run_suite() {
  local label="$1"
  printf '\n=== %s ===\n' "$label"
  shift
  if ! "$@"; then FAILED+=("$label"); fi
}

run_suite "prose linter"   python3 tests/test_lint_prose.py
run_suite "commit linter"  python3 tests/test_lint_commit.py
run_suite "git guard"      python3 tests/test_guard_git.py
run_suite "git hooks"      python3 tests/test_git_hooks.py
run_suite "installer"      bash    tests/test_install.sh
run_suite "repo integrity" python3 tests/test_repo_integrity.py

printf '\n'
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "all suites passed"
  exit 0
fi
printf 'failed suites: %s\n' "${FAILED[*]}"
exit 1
