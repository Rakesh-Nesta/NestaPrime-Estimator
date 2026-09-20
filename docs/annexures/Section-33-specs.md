# Section 33 — Draft Specifications for Director Approval

**Date: 20 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same fifth proactive gap audit as Section 32,
spot-verified against the live code before being registered as Amendment No. 27.

---

## Amendment No. 27 — Vendor Price Request Replies Ignore the Parsed GST Basis

**Registered scope (Annexure 2, §Amendment 27):** `use_vendor_reply` applies a vendor's
parsed rate literally, regardless of whether the vendor quoted it GST-inclusive or
exclusive -- silently overstating cost basis whenever a reply is GST-inclusive. A
related gap: a reply can be applied to a Cost Sheet line unrelated to the price request
it answers.

### Current state (verified against `backend/app/api/price_requests.py`, direct read)

```python
# lines 593, 618
rate_item.rate = reply.parsed_rate
...
line.rate = reply.parsed_rate
```

`VendorReply.parsed_gst_basis` (`GstBasis.INCLUSIVE`/`EXCLUSIVE`, parsed from the
vendor's free-text reply, lines 79-93) is captured, stored
(`models/price_request.py:123`), and returned in the API output -- but confirmed by
direct read and grep to be referenced nowhere inside `use_vendor_reply`. Both
`RateItem.rate` and `CostSheetLine.rate` are treated as ex-GST material rates
everywhere else in the pricing engine (`pricing.py`) -- a vendor's GST-inclusive figure
applied here directly is too high by the embedded GST%, with no error or warning.

Separately, the `COST_SHEET_LINE`/`BOTH` apply branch (lines 608-619) takes
`payload.cost_sheet_line_id` from the request with no check that the targeted
`CostSheetLine.rate_item_id` matches the `PriceRequestItem.rate_item_id` the reply
actually answers -- confirmed by direct read, no such check exists.

### Proposed spec

1. **Convert an `INCLUSIVE` reply to its ex-GST equivalent before applying it**:
   `ex_gst_rate = reply.parsed_rate / (1 + applicable_gst_percent / 100)`, where
   `applicable_gst_percent` is `rate_item.gst_percent` if set (Note R1's per-item
   override), else the global Master Setting via `get_gst_rate_percent(db)` -- the same
   resolution order `pricing.py` already uses elsewhere. An `EXCLUSIVE` reply (or one
   whose basis couldn't be parsed, `parsed_gst_basis is None`) is applied as-is, exactly
   as today.
2. **When `parsed_gst_basis is None` (ambiguous/unparseable), the apply endpoint
   requires the caller to explicitly confirm the rate is ex-GST** -- add a
   `confirmed_ex_gst: bool = False` field to `UseVendorReplyRequest`; if
   `parsed_gst_basis is None` and `confirmed_ex_gst` isn't `True`, reject with `422`
   naming the ambiguity, rather than silently assuming exclusive (today's implicit,
   undocumented behavior). This surfaces the real ambiguity to the PM/Director applying
   the reply instead of guessing on their behalf.
3. **Add the missing cross-check**: when `apply_to` includes `COST_SHEET_LINE`, reject
   with `400` if `line.rate_item_id != item.rate_item_id` (the `PriceRequestItem` the
   reply belongs to), naming the mismatch.
4. **No change to `RateHistory` logic, `MASTER`-only applies, or anything else in this
   function** -- scoped precisely to the two gaps above.

**Acceptance criteria:** a reply parsed as GST-inclusive at, say, 18% and a raw quoted
value of 118 applies an ex-GST rate of 100, not 118; a reply parsed as exclusive (or
explicitly confirmed ex-GST when ambiguous) applies unchanged; an unconfirmed ambiguous
reply is rejected with a clear `422` rather than silently applied; applying a reply to a
Cost Sheet line whose `rate_item_id` doesn't match the request's own item is rejected
with `400`.

### Open decisions — need Director input before implementation

1. **Confirm the GST-inclusive-to-exclusive conversion formula and rate-resolution
   order (item override, else global setting)** -- proposed above, matching how
   `pricing.py` already resolves the applicable rate elsewhere.
2. **Confirm requiring explicit confirmation (`confirmed_ex_gst`) when the basis is
   ambiguous**, rather than defaulting to "treat as exclusive" (today's silent
   behavior) or "treat as inclusive" (the more conservative assumption, since
   overstating cost is safer than understating it, but changes existing behavior for
   every currently-ambiguous reply). Proposed: require explicit confirmation --
   doesn't silently favor either assumption.
3. **Confirm the Cost Sheet line cross-check should hard-reject (`400`)** rather than
   just warn -- proposed as the safer default for a cost-basis-affecting mismatch.

---

## Approval

Amendment 27 (vendor reply GST-basis fix + line cross-check): ☑ Approved — "approve as
proposed, all decisions" (20 September 2026)

Decision 1 (conversion formula and rate-resolution order): ☑ Resolved as proposed.
Decision 2 (explicit confirmation when basis is ambiguous): ☑ Resolved as proposed.
Decision 3 (hard-reject the cost-sheet-line mismatch): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 20 September 2026
