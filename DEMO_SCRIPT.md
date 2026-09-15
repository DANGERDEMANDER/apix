# APix — 5-Minute Demo Script

For a judge who has never seen this system before. Time-budgeted: 5:00.

## 0:00–0:30 — What this is

"APix is a real-time airfare price index for India. It collects domestic
fare quotes across a fixed basket of routes and advance-purchase windows,
cleans and normalises them, and computes a weighted index at daily, weekly,
and monthly frequency. It is validated against DGCA reference fares and
exposed via a public read API."

Open http://localhost:5173/ — the Index Overview page.

## 0:30–1:30 — The statistical core (the hard part)

Point at the chart. "Current APix is 102.13, base-fare measure, as of
2025-10-15, coverage 100%. The line is the daily index across the collection
window."

Then open `backend/apix/index/engine.py` and read the docstring:

    APIx(t) = 100 × [ Σ_{i ∈ present} w_i × R(i,t) ] / [ Σ_{i ∈ present} w_i ]

"Every published value is computed by this formula. The interesting part is
what happens when a route is missing."

Walk through the missing-route story:

- A naive implementation would drop the missing route and sum the remaining
  weights. That biases the index toward whichever routes happened to be
  scraped.
- APix instead re-normalises the weights over the routes present, and
  stores `weight_covered`. If weight_covered < 0.70, the value is
  **withheld** — marked `insufficient_coverage` — not published.
- Show `backend/tests/test_index_engine.py::test_missing_route_re_normalisation`:
  a three-route example with one missing. The index is 103.75, not the
  biased 83.0 a naive drop would give.

"A declared gap is better than a fabricated number."

## 1:30–2:15 — Parsed vs. modelled fare decomposition

Open `backend/apix/cleaning/pipeline.py`, step 3.

"Fare quotes come in two flavours. Some sources expose the full breakup —
base fare, taxes, UDF, convenience fee. We call this **parsed**. Others only
expose a total. We apply the configured statutory model — GST 5% plus a
per-airport UDF — and mark the result **modelled**."

"The distinction matters because the index is computed on the *base fare*,
not the total. GST and UDF are policy variables, not market prices. If we
mixed parsed and modelled base fares without labelling them, a judge
looking at the index would not know what fraction of the movement was real
price change and what fraction was our model."

Show `test_parsed_decomposition_backs_out_base` and
`test_modelled_decomposition_applies_gst_and_udf`.

## 2:15–3:00 — Backtest against DGCA

Navigate to http://localhost:5173/backtest.

"APix is a statistic. It needs a reference. We compare monthly index values
against a DGCA reference table and report MAPE, Pearson r, Spearman rho,
and direction match."

Point at the chart and the stat row:

- 4 months compared
- MAPE 1.05%
- Pearson r 0.8498
- Spearman rho 0.80
- Direction match 66.7%

Then point at the provenance note at the bottom of the page:

"**These DGCA reference values are synthetic.** No machine-readable
route-level monthly average-fare table was publicly available at build
time. Rather than fabricate a number and present it as official, we tagged
every reference row SYNTHETIC and stated so in METHODOLOGY.md. The backtest
machinery is real; the ground truth is not."

That sentence is the single most important thing to say in this demo.
Fabricating an official number in front of the ministry that produces the
official numbers is the failure mode that will lose the competition.

## 3:00–3:30 — Ethics

Open ETHICS.md.

"The problem statement lists CAPTCHAs, anti-bot measures, and IP rotation
as capabilities the collector should handle, and in the same sentence
requires compliance with site terms. Those two requirements conflict."

"We implement the compliant subset — robots.txt parsing, rate limiting,
crawl delay, backoff — and we explicitly decline the non-compliant subset —
no CAPTCHA solving, no IP rotation, no anti-bot defeat. This is a deliberate
choice, not a gap. A system that respects site terms is a system the
Ministry can put its name behind."

## 3:30–4:15 — Reproducibility

In a terminal:

    uv run pytest -q

"63 tests, all green. The synthetic generator is deterministic given a
seed. The index engine is covered by Hypothesis property tests — identity,
scaling, route-order invariance, monotonicity, and weight-sum invariants."

Show one property test:

    backend/tests/test_index_properties.py::test_identity_when_prices_equal_base

"If every route's price equals its base value, the index is exactly
100.0000. Not 99.9999. Exactly. That is the identity a Laspeyres index must
satisfy."

## 4:15–4:45 — What's real and what's not

Say it plainly:

- **Real**: the statistical methodology (Laspeyres with missing-route
  re-normalisation), the cleaning pipeline, the index engine, the backtest
  metrics, the API, the dashboard, the test suite.
- **Synthetic**: the fare quotes (deliberately, so the demo runs without
  touching any live site), the DGCA reference values (no real data
  available), the route weights (pending DGCA CSV).

"This is a working prototype with a production-grade statistical core. The
remaining work is collection from real sources and loading real DGCA
reference data — not re-doing the maths."

## 4:45–5:00 — One last thing

Open `backend/tests/test_index_engine.py` and point at
`test_index_withheld_below_coverage_threshold`.

"When coverage drops below 70%, the system returns `None` for the index
value and marks the day `insufficient_coverage`. The dashboard shows a
withheld marker rather than a chart gap. That is the single design decision
that distinguishes this from a system that would publish a number on too
little data."

---

## What NOT to show

- Do not open the git log. It is not the point.
- Do not scroll through any file looking for TODOs — there are none, but
  scrolling suggests there might be.
- Do not apologise for the synthetic data. It is a deliberate, documented
  design choice. State it once, clearly, and move on.
