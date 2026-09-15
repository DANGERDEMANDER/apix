# APix — Ethics of Collection

This document states the binding policy for the APix collection layer. It
is not aspirational; the code in `backend/apix/collectors/ethics.py` (Phase
3, not yet built for this demo) implements exactly what is written here.

## What the collector does

- Fetches and caches each domain's `robots.txt` and refuses any disallowed
  path. Uses Python's `urllib.robotparser`, not a hand-rolled parser.
- Auto-disables a source whose `robots.txt` disallows the target path, with
  the reason recorded on the `sources` row
  (`robots_allows_target = false`, `robots_last_checked` = UTC timestamp).
- Honours `Crawl-delay` from `robots.txt`. Enforces a per-domain
  token-bucket rate limiter with the configured RPM ceiling.
- Sends a descriptive User-Agent including a contact URL, as research
  collection should.
- Exponential backoff with jitter on HTTP 429 and 503. A global kill switch
  (`APIX_COLLECTION_ENABLED`) halts all collection instantly.
- Collects only public search results. No passenger names, no accounts, no
  logins, no cookies, no personal data of any kind.

## What the collector explicitly does NOT do

- No CAPTCHA solving or bypass of any kind.
- No login-wall circumvention.
- No residential, rotating, or otherwise evasion-oriented proxy rotation.
- No anti-bot defeat techniques — no user-agent spoofing to impersonate a
  browser the collection is not, no TLS fingerprint manipulation, no
  session replay.
- No aggressive concurrency that would amount to a denial-of-service on
  the source. Every request is rate-limited and spaced.

## Reconciliation with the problem statement

SIH 2026 PS 26056 lists "dynamic CAPTCHAs, anti-bot measures, IP rotation,
and session management" among the capabilities the collection engine must
handle, in the same sentence requiring that collection remain "compliant
with the robots.txt and terms of service of source websites."

Those two requirements conflict. A system that rotates IPs to evade rate
limits, or solves CAPTCHAs to bypass access controls, is by definition not
respecting the source website's terms. **We implement the compliant subset
and explicitly decline the non-compliant subset.**

This is a deliberate choice, not an oversight. When a source blocks the
collector, the correct behaviour is to record a blocked event, back off,
and fall back to the replay or synthetic mode. The index engine is designed
so it cannot tell which mode produced the data; the mode is recorded on
every `collection_run` and displayed on every screen.

The reasoning: a system that respects site terms is a system that a
government ministry can put its name behind. A scraper that brags about
defeating CAPTCHAs is a liability, not a feature.

## Synthetic mode

By default, APix runs in **synthetic** mode: a deterministic generator
produces realistic fare quotes from a fixed seed without touching any
external site. This is the mode the demo uses.

- Every quote has `raw_payload.synthetic = true`.
- Every `collection_run` records `mode = 'synthetic'`.
- The API response and dashboard display the mode.

Synthetic data is never presented as real collection. The distinction is
visible on every screen.

## Replay mode

A **replay** mode exists for recorded HTML/JSON fixtures. It runs the real
parsers against local files and proves the parsing logic works without
touching a live site. Fixtures are sanitised — no cookies, no tokens, no
personal data. Fixtures are checked into `fixtures/` and reviewed before
commit.

## Live mode

**Live** network collection is disabled by default behind
`APIX_ENABLE_LIVE=true`. When enabled, all the safeguards above apply:
robots.txt is checked first, rate limits are enforced, and a robots-disallowed
source is auto-disabled rather than retried.

## Provenance of every number

Every value shown in the dashboard is traceable to a row in the database.
`collection_runs.mode` records whether each row came from `synthetic`,
`replay`, or `live` collection. `routes.weight_source` records whether each
route's weight came from `dgca-published` or `dgca-synthetic` reference
data. `dgca_reference.source_note` records the provenance of every backtest
reference value.

Nothing is presented as something it is not.
