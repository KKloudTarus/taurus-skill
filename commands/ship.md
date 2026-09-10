---
description: Pre-commit audit, then commit and optionally open a PR under git-discipline
argument-hint: [commit subject]
---

Prepare this change for shipping with subject hint
**${ARGUMENTS:-derive from the diff}**.

Load the `taurus` skill, then read `references/git-discipline.md`,
`references/conventional-commits.md`, and `references/writing-voice.md`.

## 1. Audit the tree

```
git status --porcelain
git diff --cached
git diff
git ls-files | grep -E '(^|/)(CLAUDE\.md|AGENTS\.md|\.mcp\.json|\.claude/)' || echo "clean"
grep -nE '(^|/)\.claude/?$|^CLAUDE\.md$' .gitignore || echo "gitignore missing entries"
```

Read the full diff. Check for secrets, tokens, `.env` contents, keys, debug prints,
commented-out code, and stray TODOs. Confirm no `.claude/`, `CLAUDE.md`,
`AGENTS.md`, or `.mcp.json` is tracked or staged. Fix `.gitignore` in its own commit
when entries are missing.

## 2. Confirm green

Apply the checks required by the tier in `references/engineering-baseline.md`. A failed
applicable check does not ship. Confirm the gate report matches this exact tree:

```
python3 ~/.claude/taurus/hooks/gate-report.py validate
```

Run `/verify` when the report is missing, red, or stale.

## 3. Branch

Refuse to commit on `main`, `master`, or `production`. Create
`<type>/<short-kebab-summary>` first, using a commit type as the branch type.

## 4. Commit

Conventional Commits 1.0.0: `<type>[(scope)][!]: <description>`, imperative, lowercase,
subject 72 characters or fewer, no trailing period, blank line, body explaining why, blank
line, footers. Breaking changes take `!` after the type or scope, a `BREAKING CHANGE:`
footer, or both.

Split into atomic commits when the diff carries more than one intent, each one building
and passing tests on its own. A diff that fits two types is two commits.

Run both checks on the message before committing:

```
python3 ~/.claude/taurus/hooks/lint-commit.py --stdin <<'EOF'
<the message>
EOF

python3 ~/.claude/taurus/hooks/lint-prose.py --stdin --profile commit <<'EOF'
<the message>
EOF
```

Both must exit 0. No AI attribution, no trailers, no emoji.

## 5. Pull request

Only when asked. The title follows the same grammar as the lead commit, because a squash
merge turns it into the commit subject:

```
python3 ~/.claude/taurus/hooks/lint-commit.py --stdin --pr-title <<< "$PR_TITLE"
```

Use the `references/git-discipline.md` PR template: Problem, Approach, Alternatives
rejected, Risk and rollback, Verification. A breaking change is stated in the title with
`!` and repeated under Risk and rollback. Prose follows `references/writing-voice.md`.

Never push without being asked. Never force-push a shared branch.
