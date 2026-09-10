> Load when: A draft feels stiff, generic, over-polished, too compressed, or disconnected from the reader, or when a prose-linter warning needs contextual judgment. Provides rewrites for chat, reviews, commits, PRs, design docs, comments, and incident notes.

# Rewrite catalogue

Use these examples to recover a natural voice, not as templates to copy word for
word. Keep the facts and adjust the tone to the reader and the artifact.

<!-- prose-lint-disable -->

## Chat replies

Stiff: Pool size hiện là 20. Queue giữ 400 request. p99 đạt 1.8s. Nâng pool lên 60.

Natural: Ừ, khả năng cao là pool đang nghẽn. Giới hạn hiện tại là 20 connection,
trong khi giờ cao điểm có khoảng 400 request chờ và p99 lên tới 1.8 giây. Benchmark
với 60 connection đưa p99 xuống dưới 300 ms, nhưng nên kiểm tra database headroom
trước khi đổi để tránh đẩy bottleneck sang chỗ khác.

Why it works: the reply answers early, connects the evidence, and leaves the reader
with a sensible next check. The acknowledgement responds to the situation instead of
praising the question.

## Review comments

Stiff: This is not just a style issue, it's a correctness issue. It might potentially
cause problems under load.

Natural: Chỗ này có race condition. Hai request có thể cùng vượt qua availability
check trước khi request nào kịp ghi. Dùng `SELECT FOR UPDATE` trên `seat_hold`, hoặc
thêm unique constraint cho seat đang ở trạng thái `HELD`.

Stiff: Cache ở dòng 88 có TTL 5 phút. User thấy giá cũ. Invalidate cache.

Natural: Cache ở dòng 88 giữ giá trong 5 phút, nên user vẫn có thể thấy giá cũ sau
khi organizer sửa price book. Nếu giữ cache này, hãy invalidate khi nhận
`PriceBookUpdated`; nếu browse path chưa cần cache, bỏ nó sẽ đơn giản hơn.

## Commit messages

Stiff: `fix: improve payment reliability`

Natural:

```
fix(payment): reject stale webhook signatures

A replayed capture webhook could enter the fulfilment path twice. The handler now
rejects signatures older than five minutes and records the event id before doing
any work.

Refs: PLAT-901
```

## PR descriptions

Stiff: This PR implements a comprehensive solution that makes seat holding robust
and scalable.

Natural:

```markdown
## Problem

Two checkouts on different pods could reserve the same seat. The availability check
ran against Redis, while the final write happened in Postgres, so the two operations
were not atomic. The contention test reproduced 12 double reservations in 200 runs.

## Approach

Seat holds now write to `inventory.seat_hold` in the same transaction that checks
availability, under a row lock on the selected seats. Redis remains a projection for
the browse path and no longer decides whether a hold succeeds.
```

## Design docs

Stiff: Payment consistency is critical. Idempotency is required at multiple layers.
Therefore, a comprehensive solution is needed.

Natural: A payment intent may be retried by both the client and the PSP, but it may
only be charged once. Payment service stores the idempotency record in Postgres in
the same transaction as the state change. Redis can reject obvious duplicates early;
it is not the source of truth.

## Code comments

Stiff: `// We use a mutex here for safety.`

Natural: `// seatCache is read by the SSE broadcaster and written by the Kafka consumer.`

Delete a comment that only translates the next line into English.

## Incident notes

Conversational: Có vẻ database hơi chậm nên checkout timeout. Bây giờ hệ thống đã ổn.

Operational: Từ 14:02 tới 14:19, checkout p99 tăng lên 9 giây. Migration
`ALTER TABLE orders` giữ table lock trong 17 phút, làm 340 checkout timeout; không có
double charge. Rollback hoàn tất lúc 14:19, và p99 trở lại 280 ms lúc 14:22.

Incident notes should stay dry because readers need an exact timeline. Natural voice
does not require every artifact to sound casual.

<!-- prose-lint-enable -->

## Four questions for a draft

1. Does this sound like a response to this reader, or could it appear unchanged in
   any conversation?
2. Are related facts connected, or did compression turn them into fragments?
3. Does every number and certainty level come from evidence?
4. Would the reader know what to do next without a ceremonial closing paragraph?
