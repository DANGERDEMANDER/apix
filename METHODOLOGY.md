# APix — Methodology

This document states the formula, every assumption, and the known
limitations of the Airfare Price Index for India (APix). It is the
authoritative prose description. Where it and the code disagree, the code
wins and this document is wrong.

## 1. Scope

APix measures the change in the price of a fixed basket of domestic air
travel, expressed as an index number with base = 100. It is computed at
daily, weekly, and monthly frequencies, on two measures:

- **base** — the base fare only (excludes taxes, UDF, convenience fees)
- **total** — the fare a passenger actually pays

The base-fare series is the primary one. It isolates the price of air
transport as a service from the tax component, matching how CPI treats
taxes in other categories. The total-fare series is published alongside so
that the effect of tax changes is visible.

## 2. Basket

Ten domestic routes, selected to cover the six corridors named in SIH 2026
PS 26056 plus four additional high-traffic sectors:

    DEL-BOM   DEL-BLR   BOM-BLR   DEL-CCU   BLR-HYD   MAA-DEL
    DEL-HYD   BOM-HYD   DEL-AMD   BLR-CCU

Route weights are annual passenger counts from DGCA, normalised across
active routes so that they sum to exactly 1.000000 at six decimal places.
The rounding residual is assigned to the first route so the sum holds
exactly, not just approximately.

**Provenance of weights.** Every route carries a `weight_source` field:

- `dgca-published` — loaded from a real DGCA CSV in `data/dgca/route_pax.csv`
- `dgca-synthetic` — a placeholder used when no real CSV is present

In this build the demo data is synthetic. METHODOLOGY.md says so plainly:
**the weights shown in the current demo are placeholders pending real DGCA
data. The weighting methodology is real; the ground truth is not.** The
dashboard marks synthetic weights with an amber tag.

## 3. Advance-purchase windows

For each route and each collection date t, quotes are collected across
five advance-purchase windows: 1, 7, 15, 30, and 45 days before departure.

The windows are aggregated with booking-profile weights v_w:

    v = { T+1: 0.05, T+7: 0.15, T+15: 0.25, T+30: 0.30, T+45: 0.25 }
    Σ v_w = 1.0

**Assumption.** These weights approximate the distribution of booking lead
times in the Indian domestic market. MoSPI's Expert Group for the new CPI
series recommended a single 7-day advance-purchase window; APix uses five
because a single point on the booking curve cannot capture the pricing
heterogeneity that travellers actually face. The weights are configurable
in `config/index.yaml` and can be replaced with calibrated values when a
longer data history exists.

## 4. Window aggregation (spec §7.1)

For route i on collection date t, the route price P(i,t) is:

    P(i,t) = Σ_w  v_w × median{ clean base fares for (i, t, window w) }

The **median** within a window is robust to a single bad source. The
**weighted mean across windows** uses the configured v_w.

If a window has zero accepted quotes, the remaining weights are
**re-normalised** so they sum to 1.0 over the windows present.

Rationale for median rather than geometric mean: median is robust to one
mis-priced quote from one source; Jevons (used by BLS) is not. The trade-off
is that median is less sensitive to genuine price dispersion across
carriers. The choice is documented here rather than hidden in code.

## 5. Price relative (spec §7.2)

    R(i,t) = P(i,t) / P(i,0)

where P(i,0) is the arithmetic mean of P(i,t) over the base period. Base
values are stored in a dedicated `index_base_values` table so the index is
reproducible.

**Base period.** Default: the first 14 complete collection days, where
"complete" means weight_covered ≥ 0.70 on that day. A route must appear on
at least `base_period_min_route_days` (default 10) of those days to anchor.

MoSPI CPI 2024 uses calendar year 2024 as its base. APix uses a rolling
first-N-days base because the system is designed for real-time operation
from first boot. The base period is stored in the database and can be rolled
forward to a fixed calendar period once a full year of data exists.

## 6. Weights (spec §7.3)

    w_i = dgca_pax_annual_i / Σ dgca_pax_annual

over active routes. See §2 for provenance.

## 7. The index (spec §7.4)

    APIx(t) = 100 × [ Σ_{i ∈ present} w_i × R(i,t) ] / [ Σ_{i ∈ present} w_i ]

where "present" means routes that have both a price P(i,t) today and a base
value P(i,0).

**Missing-route handling.** If a route has no price on day t, we do NOT drop
it and sum the remaining weights. That would bias the index toward whichever
routes happened to be scraped — the exact failure mode that would make a
competitor's naive implementation statistically wrong.

Instead, weights are re-normalised over the routes actually present, and
`weight_covered = Σ_{i ∈ present} w_i` is stored with every index value.

**Withholding rule.** If weight_covered < 0.70, no number is published for
that day. The index value row is written with
`status = 'insufficient_coverage'` and a human-readable `withheld_reason`.
The API and dashboard surface this. **A declared gap is better than a
fabricated number.**

## 8. Weekly and monthly (spec §7.5)

- **Weekly** = unweighted mean of published daily values over the ISO week,
  requiring ≥ 5 published days.
- **Monthly** = unweighted mean of published daily values over the calendar
  month, requiring ≥ 20 published days.

Months and weeks that fail the minimum-day threshold are withheld. This is
why the current demo produces a monthly value for October 2025 only when the
collection window covers the full month; a partial month is not published.

MoM and YoY percentages are computed from the published values.

## 9. Known limitations

1. **Synthetic data.** The demo's fare quotes and DGCA reference values are
   synthetic. Real DGCA figures are not currently loaded because no
   machine-readable route-level monthly average-fare table was publicly
   available at build time. The methodology is real; the ground truth is
   not. See §12 of the build spec.

2. **Festival surge model.** The synthetic generator applies festival
   multipliers in departure-date space only. This produces a visible ramp
   in the index over a few days when a festival enters the 45-day departure
   window, which is faster than a real festival surge. The daily index in
   August–September 2025 shows this artifact. It does not invalidate the
   methodology; it is a property of the synthetic generator.

3. **Window weights are a prior.** The v_w vector is an assumption. Once a
   longer history exists, `apix calibrate` (future work) will fit v_w to
   DGCA monthly reference by least-squares with an L2 penalty toward the
   prior. The prior is preserved under `window_weights_prior` in config.

4. **Weekly/monthly values are keyed by representative date.** Because the
   §6 schema has no separate week-key or month-key column, weekly and
   monthly index values are stored under the last published day of the
   period. A dedicated key column is a Phase 8 polish item.

5. **Coverage-weighted vs unweighted weekly/monthly.** The spec calls for an
   unweighted mean of daily values. A coverage-weighted mean — Σ(wc_t ×
   APIx_t) / Σ wc_t — would be more defensible statistically because days
   with lower coverage would contribute less. We follow the spec and
   document the trade-off here.

## 10. Backtest against DGCA (spec §12)

`apix backtest` compares monthly APix against the `dgca_reference` table
and reports four metrics:

- **MAPE** — mean absolute percentage error, after rebasing both series
  to 100 at the first common month
- **Pearson r** — linear correlation between the two rebased series
- **Spearman ρ** — rank correlation
- **Direction match** — percentage of month-over-month changes that agree
  in sign

**Provenance.** The reference values currently loaded into
`dgca_reference` are synthetic, tagged with `SYNTHETIC placeholder pending
real DGCA data` in `source_note`. Every value on every screen traces back
to a row in the database, and every reference row carries its provenance
tag. We do not present a fabricated number as if it were an official DGCA
figure.
