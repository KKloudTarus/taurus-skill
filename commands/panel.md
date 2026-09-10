---
description: Convene a 2-3 agent review panel on a decision or a review, then synthesize without deferring to any agent
argument-hint: <the question, or the code/design to review>
---

Convene a review panel on: **$ARGUMENTS**

Load the `taurus` skill, then read `references/review-panel.md` and follow the protocol.

1. **Freeze the question** in one sentence with a decidable outcome. Write the
   decision criteria with weights, and the constraints, before spawning anything.
   Show them.
2. **Choose the panel.** Three agents for a tier 0 or irreversible decision, two
   otherwise.
   - Reviewing code: `architecture-critic`, `qa-verifier`, plus `security-auditor`,
     `performance-auditor`, `algorithm-verifier`, or `reliability-auditor` depending
     on what the change touches. Use `platform-auditor`, `frontend-quality-auditor`,
     or `ai-ml-verifier` when that is the risk the decision needs to expose.
   - Deciding between options: one `decision-analyst` per option, plus a third
     agent mandated to attack every option and to name the option nobody proposed.
3. **Brief them identically on facts, differently on mandate.** Never tell a
   panelist what you think, what another panelist thinks, or which option you wrote.
   Label options neutrally. Send all agents in a single message.
4. **Synthesize.** Open the files and check every finding yourself. Classify each as
   confirmed, plausible, or rejected. Resolve conflicts with evidence, never by vote
   count and never by which agent sounded certain. When the panel splits with no
   evidence, run the smallest experiment that produces some.
5. **Report** in `references/review-panel.md` format, including the dissent and why it lost.

The synthesis is your answer and you own it. Do not paste the panel's raw output
as the conclusion.
