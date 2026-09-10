> Load when: a draft was flagged by the writing standard and the fix is not obvious, or when rewriting a chat reply, review comment, commit message, PR body, design doc, code comment, or incident note.

# Rewrite catalogue

Before and after, drawn from real review comments, PR bodies, and design docs.
Load when a draft is flagged and the fix is not obvious.

<!-- prose-lint-disable -->

## Chat replies

Before: Great question! Điều này là một vấn đề thú vị. Về cơ bản, connection pool có thể đang bị đầy — điều này dẫn tới việc request bị treo. Tóm lại, bạn nên tăng pool size.

After: Pool đang giới hạn ở 20 connection. Ở peak có 400 request chờ, nên p99 chạm 1.8s. Nâng lên 60 giữ p99 dưới 300ms trong benchmark ở tests/load/pool_test.go.

What changed: the filler opener, the meta sentence, the hedge stack, the em dash,
and the closing summary all went. The numbers and the file path came in.

## Review comments

Before: This is not just a style issue, it's a correctness issue. It might potentially cause problems under load.

After: Two requests can both pass the availability check before either writes. Add SELECT FOR UPDATE on seat_hold, or a unique constraint on (occurrence_id, seat_id) where state = 'HELD'.

Before: Đây là một thiết kế tốt, tuy nhiên có lẽ nên xem xét lại việc sử dụng cache ở đây.

After: Cache ở dòng 88 giữ TTL 5 phút nhưng giá đổi ngay khi organizer sửa price book. User thấy giá cũ tới 5 phút. Invalidate theo event PriceBookUpdated, hoặc bỏ cache ở path này.

## Commit messages

Before: fix: fixed some issues with the payment flow — this makes it more robust

After:

```
fix(payment): reject a webhook whose signature timestamp is over 5 minutes old

A replayed capture webhook re-ran the fulfilment path and issued a second
ticket. The handler now checks the timestamp against a 5-minute window and
records the event id before doing any work.

Refs: PLAT-901
```

## PR descriptions

Before: ## Summary\nThis PR implements a comprehensive and robust solution for seat holding. It's not just a fix — it's a rethinking of how we handle inventory. Overall, this should significantly improve reliability.

After:

```markdown
## Problem
Two checkouts on different pods could both win the same seat. Redis held the
hold state, so the availability check and the write were not atomic. Reproduced
in tests/inventory/contention_test.go: 12 double-sells out of 200 attempts.

## Approach
The hold now writes to inventory.seat_hold inside the transaction that checks
availability, under SELECT FOR UPDATE on the seat rows. Redis keeps the
availability projection for the browse path only.
```

## Design docs

Before: Việc đảm bảo tính nhất quán của quá trình xử lý thanh toán là một yêu cầu quan trọng. Điều này đòi hỏi khả năng xử lý idempotency ở nhiều tầng khác nhau. Do đó, chúng ta cần một giải pháp toàn diện.

After: Một payment intent chỉ được charge đúng một lần, kể cả khi client retry hoặc PSP gửi webhook trùng. Payment service ghi idempotency state vào Postgres trong cùng transaction với charge. Gateway cache key ở Redis chỉ để chặn sớm, không phải nguồn sự thật.

## Code comments

Before: // This function processes the order on func processOrder(...).

After: delete it.

Before: // We use a mutex here for safety

After: // seatCache is read by the SSE broadcaster and written by the Kafka consumer.

## Incident notes

Before: Có thể do database bị chậm, dẫn đến việc timeout. Nhìn chung hệ thống đã ổn định trở lại.

After: Từ 14:02 tới 14:19, checkout p99 lên 9s. Nguyên nhân: migration ALTER TABLE orders khoá bảng 17 phút. 340 checkout timeout, 0 double-charge. Rollback lúc 14:19.

<!-- prose-lint-enable -->

## The three questions for any draft

1. Which sentence carries the fact the reader needs? Put it first.
2. Which sentences would the reader still understand the draft without? Cut them.
3. Which claim has no number, no file, and no test behind it? Get one, or drop the claim.
