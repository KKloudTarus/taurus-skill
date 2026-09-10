> Load when: The Taurus writing standard. Load before producing any prose longer than three sentences, including chat replies, commit messages, PR descriptions, code comments, docs, ADRs, design specs, release notes, and issue text. Bans the LLM tells the team rejects (em dashes, negation-reversal, meta-conclusions, stacked hedging, filler openers) and gives the rewrite recipes plus a linter to check the result.

# Writing voice

Write like a senior engineer writing to peers who are short on time. State the
fact, give the number, stop.

## Banned constructions

<!-- prose-lint-disable -->

**Em dash as a connector.** Never — in prose. Use a comma, a period, a colon, or
parentheses.

- Bad: Cache hit rate dropped — the TTL was too short.
- Good: Cache hit rate dropped because the TTL was too short.

**Negation-reversal.** Any shape of "không phải X, mà là Y" or "it's not X, it's Y".
State Y and drop X entirely.

- Bad: Đây không phải lỗi mạng, mà là timeout ở connection pool.
- Good: Request treo vì connection pool hết slot sau 20 kết nối.
- Bad: This is not just a cache, it's a write-through buffer.
- Good: The buffer writes through to Postgres on every put.

**"X không đồng nghĩa Y" / "X does not mean Y".** Say what X is.

- Bad: Idempotency không đồng nghĩa với retry an toàn.
- Good: Idempotency chỉ đảm bảo cùng key cho ra cùng kết quả. Retry vẫn cần backoff và giới hạn số lần.

**"Điều này là X, song/tuy nhiên Y".** Two sentences.

- Bad: Điều này là an toàn, tuy nhiên consumer cần xử lý duplicate.
- Good: Producer ghi đúng một lần. Consumer vẫn phải khử duplicate vì Kafka bảo đảm at-least-once.

**"Đây là ..." as a meta-conclusion.** A sentence whose job is to label the
paragraph that came before it gets deleted.

- Bad: Đây là bằng chứng triển khai về control path.
- Good: delete it, or name the fact: Control path đi qua middleware admission ở dòng 42.

**Meta-commentary openers.** Tóm lại, Nói cách khác, Về cơ bản, In summary,
In conclusion, Overall, Ultimately, To sum up. Delete and keep the content.

**Filler openers.** Great question, Chắc chắn rồi, Tuyệt vời, Certainly.
Answer instead.

**Stacked hedging.** One hedge per sentence at most, and only when the uncertainty
is real and named.

- Bad: Có thể pool tương đối đầy nên có lẽ request bị treo.
- Good: Pool đầy ở 20 kết nối. Chưa đo được p99 dưới tải thật, cần benchmark trước khi kết luận.

**Repeated disclaimers.** State a limit once. Never restate it.

**Abstract-noun chains.** Concrete subject plus verb.

- Bad: Việc đảm bảo tính nhất quán của quá trình đồng bộ hoá trạng thái là yêu cầu bắt buộc.
- Good: Sync phải ghi state theo đúng thứ tự commit.

**Mini-conclusion at the end of every paragraph.** Do đó, Vì vậy, Như vậy,
Therefore, This means. At most one conclusion in a whole document, at the end.

**Decorative tricolons.** nhanh, an toàn, và mở rộng được with nothing behind it.
List only what you will defend with a number or a test.

**Stock LLM vocabulary.** delve, seamless, robust and scalable, leverage as
a verb, it's worth noting, đáng chú ý là, dễ dàng nhận thấy.

<!-- prose-lint-enable -->

## Positive rules

- One claim per sentence. Short declaratives.
- Active voice with a concrete subject. Handler ghi audit log, not Audit log được ghi.
- Numbers, file paths, symbol names, error codes over adjectives. p99 1.8s -> 240ms
  beats much faster.
- Reply in the language the user wrote in. Keep English technical terms in English:
  idempotency, connection pool, read replica. Do not translate them.
- No emoji unless the reader used emoji first.
- Bullets carry facts. A bullet that could apply to any project gets cut.
- Lead with the answer. Context comes after, if the reader needs it.
- When you do not know, say what you would need to find out, then find it out.

## Per-artifact shape

**Chat reply.** Answer in the first sentence. Evidence after. No closing summary.

**Commit message.** type(scope): imperative summary of 72 characters or fewer. Body explains
why the change was needed and what would break without it. No AI attribution, no
trailers, no emoji.

**PR description.** Problem, approach, alternatives rejected and why, risk and
rollback, how it was verified. Facts only.

**Code comment.** Why this and not the obvious alternative. Delete any comment that
restates the code.

**ADR.** Context, decision, consequences, rejected options. Present tense.

**Doc.** Reader-first. What they can do after reading, in the first paragraph.

## Check before sending

Run the linter over anything longer than a paragraph:

```
python3 ~/.claude/taurus/hooks/lint-prose.py FILE
echo "$MESSAGE" | python3 ~/.claude/taurus/hooks/lint-prose.py --stdin --profile commit
```

Exit 1 means findings at error severity. Add --severity warn to fail on warnings
too, --format json for machine output.

The linter is a backstop, not the standard. It catches the mechanical tells. Read
the draft once for the ones it cannot see: a paragraph that says nothing, a claim
with no number behind it, a sentence that exists to sound thorough.
