---
description: Lint text or files against the Taurus writing standard and rewrite the findings
argument-hint: [file ...] (defaults to changed markdown files)
---

Check writing against the standard: **${ARGUMENTS:-changed markdown and docs on this branch}**

Load the `taurus` skill, then read `references/writing-voice.md`.

1. Resolve the target files. With no argument, use
   `git diff --name-only HEAD -- '*.md' '*.mdx' '*.txt'` plus any untracked ones.
2. Run the linter:

```
python3 ~/.claude/taurus/hooks/lint-prose.py --severity warn <files>
```

3. Rewrite every error finding. For each one, show the before and after line so the
   change is reviewable. Warnings get judgment: fix the ones that are real, and say
   which you kept and why.
4. Read the result once for what the linter cannot see: a paragraph that says
   nothing, a claim with no number behind it, a sentence written to sound thorough,
   a conclusion the reader already reached two lines earlier.
5. Re-run the linter and show it clean.

Rewrite the prose. Never rewrite code inside fenced blocks.
