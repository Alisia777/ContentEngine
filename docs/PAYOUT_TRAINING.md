# Payout Training

Payout Basics explains how ledger entries are calculated and why traceability is mandatory.

## Payout Types

- `per_video`
- `per_approved_post`
- `per_published_post`
- CPA
- revenue share
- hybrid

## Statuses

- `pending`
- `approved`
- `payable`
- `paid`
- `rejected`
- `disputed`

The system records payout ledger entries. It does not execute real payments or store payment secrets.

## Traceability Rule

`per_published_post` requires a publishing task with `final_url`.

Without `final_url`, ContentEngine cannot prove the post exists and should not calculate that payout.

## Certification Questions

- Can `per_published_post` payout be calculated without `final_url`? Correct answer: no.
- Does ContentEngine execute real payments? Correct answer: no.
