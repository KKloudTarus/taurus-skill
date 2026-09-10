> Load when: Writing a commit message, a PR title, a tag, or a changelog entry. Carries the full Conventional Commits 1.0.0 grammar the guard enforces, the allowed type list, scope and footer rules, both breaking-change forms, and the local validator commands. Read it before the first commit in any repo.

# Conventional Commits 1.0.0

Specification: https://www.conventionalcommits.org/en/v1.0.0/

Every commit message and every PR title in every repo follows it.
`hooks/lint-commit.py` owns the grammar. It runs in two places: inside git as a
`commit-msg` hook, and in the session as part of the `PreToolUse` guard. A message that
fails it does not reach the history.

## Structure

```
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

Four structural requirements, all checked:

1. The subject starts with a type, then an optional `(scope)`, then an optional `!`,
   then a colon and one space.
2. The description follows immediately after that colon and space.
3. The body starts one blank line after the subject.
4. The footers start one blank line after the body.

## Types

`feat` and `fix` are mandated by the spec. The rest is the Angular set the spec points
at, fixed to a closed list so changelog and release tooling stay deterministic.

| Type | Use for | SemVer |
|---|---|---|
| `feat` | a new capability in the product | MINOR |
| `fix` | a bug patched in the codebase | PATCH |
| `perf` | a change that only improves speed or resource use | PATCH |
| `refactor` | restructuring with no behavior change | none |
| `test` | tests added or corrected on their own | none |
| `docs` | documentation only | none |
| `build` | build system, dependencies, packaging | none |
| `ci` | pipeline config and CI scripts | none |
| `style` | formatting with no semantic effect | none |
| `chore` | maintenance that fits nothing above | none |
| `revert` | undoing an earlier commit | depends on what was reverted |

Types are lowercase. The spec permits any casing and asks for consistency; this pack
picks lowercase and enforces it.

When a change fits two types, split it into two commits. That is the point of the
convention, and it is what the spec's own FAQ recommends.

## Scope

A scope is one lowercase noun naming the section of the codebase, in parentheses,
directly after the type.

```
feat(inventory): hold seats under a row-level lock
fix(internal/order): release the hold when payment times out
```

Allowed characters: lowercase letters, digits, `.`, `_`, `/`, `-`. No spaces, no empty
parentheses. Pick scope names from the repo's own vocabulary (a bounded context, a
package, a service) and keep them stable, since scopes end up as changelog sections.

Omit the scope when the change spans the whole repo.

## Description

Imperative mood, lowercase first letter, no trailing period, subject line of 72
characters or fewer including the type and scope.

```
fix(pool): raise max conns to 60 so p99 stays under 300ms     good
Fix(Pool): Raised the max connections.                        rejected
fix: stuff                                                    useless
```

The description says what the commit does to the codebase. It does not describe the
diff line by line, and it does not restate the ticket title.

## Body

Free-form, one blank line after the subject, any number of paragraphs. The body answers
why. The diff already says what.

Name the evidence: the error, the metric, the reproduction, the benchmark. State
complexity when the change touches an algorithm or a query.

## Footers

One blank line after the body. Each footer is a token, a separator, and a value.

- Separator: `:` followed by a space, or a space followed by `#`.
- The token uses `-` in place of any whitespace: `Reviewed-by`, `Signed-off-by`,
  `Co-authored-by`, `Refs`, `Closes`.
- `BREAKING CHANGE` is the one token allowed to contain a space, and it MUST be
  uppercase. `BREAKING-CHANGE` means the same thing.
- A footer value may run across several lines. Parsing stops at the next valid token.

```
Refs: PLAT-812
Closes #412
Reviewed-by: Z
```

`Reviewed by: Z` is rejected, because a footer token uses hyphens.

No AI attribution reaches a footer. `Co-Authored-By: Claude`, `Generated with Claude
Code`, and any Claude or Anthropic mention are blocked by the same guard, in every repo
including this one.

## Breaking changes

Two forms, both valid, both may appear together.

`!` before the colon, when the description alone explains the break:

```
feat(api)!: drop the v1 Accept header
```

A `BREAKING CHANGE:` footer, when callers need migration steps:

```
feat(config): load config through the extends chain

BREAKING CHANGE: the extends key now points at another config file.
Callers passing an inline object must move it into a file first.
```

A breaking change maps to MAJOR in SemVer regardless of type, so `fix!` and `chore!`
are both legitimate. Use the footer whenever a reader would otherwise have to read the
diff to learn what to change.

## Reverts

The spec leaves revert handling to tooling. House rule: use the `revert` type and name
the reverted SHAs in a footer.

```
revert: feat(cache): add the write-through path

Refs: 676104e
```

Messages that git generates itself are left alone by the validator: `Merge ...`,
`Revert "..."`, `fixup!`, and `squash!`.

## Pull requests

The PR title follows the same grammar as the lead commit, because a squash merge turns
it into the commit subject. GitHub appends ` (#412)` on squash; the validator ignores
that suffix in `--pr-title` mode.

```
feat(gateway): add the route policy registry (#412)
```

The PR body follows the template in `git-discipline.md`.

## Validate before committing

```
python3 ~/.claude/taurus/hooks/lint-commit.py --stdin <<'EOF'
feat(inventory): hold seats under a row-level lock
EOF

python3 ~/.claude/taurus/hooks/lint-commit.py --stdin --pr-title <<< "$PR_TITLE"
python3 ~/.claude/taurus/hooks/lint-commit.py .git/COMMIT_EDITMSG
```

Exit 0 passes, exit 1 reports findings. Add `--severity warn` to fail on warnings too,
and `--format json` for tooling.

`install.sh` already wires this into every repo through `core.hooksPath`, so the rule
holds for commits made outside a session. Check it:

```
git config --global --get core.hooksPath
```

## Two layers

The rule is enforced twice, because one layer alone cannot hold it.

| Layer | Sees | Can be routed around by |
|---|---|---|
| `githooks/commit-msg` | the final message git assembled | nothing, short of `--no-verify` |
| `hooks/guard-git.py` (`PreToolUse`) | a command string, before it runs | any spelling bash and git agree on and the guard does not |

`install.sh` points `core.hooksPath` at the pack's `githooks/`, so `commit-msg`,
`pre-commit`, and `pre-push` run in every repo on the machine. The guard blocks
`--no-verify`, since that flag exists to skip the layer that actually holds.

`core.hooksPath` replaces a repository's hook directory outright, so `githooks/` also
ships a passthrough for every other client-side hook name. Each one enforces nothing
and hands control to `.git/hooks/<name>`, with stdin intact. Without them, installing
this pack would silently stop `prepare-commit-msg`, `post-commit`, husky, lefthook and
every other repo hook on the machine.

The guard is the fast layer: it fails in the session, where the message can be fixed
before git is ever called. Two rounds of adversarial review found nine and then twelve
ways to spell a command past it, which is what a command-string parser competing with
bash and git parse-options gets you. It stays useful and it is not the control.

## What the guard can and cannot see

The `PreToolUse` guard reads a command string that bash and git each parse by their
own rules. Three parsers never agree, so the guard fails closed: where it cannot read
a command with confidence, it blocks and says why.

It refuses these because the real message is hidden from every check:

```
git commit -m "$(cat msg.txt)"      command substitution
git commit -F -                     the message arrives on stdin
git commit -F <(generate)           process substitution
git commit -m $'...'                ANSI-C quoting bash expands and shlex does not
bash -c "git commit -m ..."         a nested shell
git commit -F not-written-yet.txt   the file does not exist when the hook runs
```

Two spellings work in every case: `-m` once per paragraph, or a message file written
in its own command and passed with `-F <file>`.

```bash
cat > /tmp/msg.txt <<'EOF'
feat(inventory): hold seats under a row-level lock

Redis held the seat state, so two checkouts could both win the same seat.
EOF
git commit -F /tmp/msg.txt
```

The message file must be a regular file under 64 KiB, and its contents never appear in
a guard error, so a wrong path cannot leak a file into the transcript.

## Rules the validator enforces

| Rule | Meaning |
|---|---|
| `header-no-type` | the subject carries no type prefix |
| `header-no-space` | the colon is not followed by a space |
| `header-no-description` | a type prefix with nothing after it |
| `header-leading-space` | the subject starts with whitespace |
| `header-malformed` | the subject matches no valid shape |
| `header-too-long` | the subject is over 72 characters |
| `type-case` | the type is not lowercase |
| `type-unknown` | the type is outside the allowed list |
| `scope-empty` | empty parentheses |
| `scope-format` | the scope carries spaces or uppercase |
| `description-period` | the description ends with a period |
| `description-leading-space` | more than one space after the colon |
| `description-case` | the description starts with a capital (warning) |
| `blank-line-before-body` | the body does not start one blank line down |
| `breaking-change-case` | the breaking token is not uppercase |
| `breaking-change-empty` | the breaking footer has no description |
| `breaking-change-separator` | the breaking token is not followed by a colon and a space |
| `breaking-change-not-a-footer` | the breaking token sits in the body |
| `breaking-change-undocumented` | `!` with no footer explaining it (warning) |
| `footer-token-whitespace` | a footer token uses spaces where `-` belongs |

## Worked example

```
feat(inventory)!: hold seats under a row-level lock

Redis held the seat state, so two checkouts on different pods could both
win the same seat. The hold now writes to inventory.seat_hold inside the
same transaction that checks availability.

Contention is O(1) per seat under the row lock. A 200-goroutine test
produced 1 winner and 199 SEAT_UNAVAILABLE.

BREAKING CHANGE: HoldSeats no longer accepts a Redis client. Callers
construct it with a pgx pool.

Refs: PLAT-812
Reviewed-by: Z
```
