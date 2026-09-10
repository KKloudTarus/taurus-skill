---
description: Review text for a natural technical voice and use the prose linter as a supporting signal
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

3. Fix every publishing-policy error. Treat warnings as prompts to reread the passage,
   not instructions to replace a word mechanically. Keep useful transitions,
   contrasts, and signs of warmth.
4. Read the result aloud. Check whether it responds to this reader, whether related
   facts flow together, whether sentence lengths vary, and whether the level of detail
   fits the conversation. Remove unsupported precision and report-like formatting.
5. Re-run the linter. Report any warning you intentionally kept and why it helps.

Rewrite the prose. Never rewrite code inside fenced blocks.
