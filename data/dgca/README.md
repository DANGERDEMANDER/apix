# DGCA reference data

This directory holds the ground-truth fares used for the monthly backtest in
Phase 5. Two CSV files are read if present.

## `route_pax.csv` — annual passenger counts for route weighting

Format:

```csv
label,dgca_pax_annual
DEL-BOM,8500000
DEL-BLR,5200000
```

When this file is present, `apix seed` reads it and tags every route with
`weight_source = 'dgca-published'`. When absent, the loader falls back to the
synthetic placeholder table in `apix/seed/basket.py` and tags routes with
`weight_source = 'dgca-synthetic'`. `METHODOLOGY.md` states this plainly.

## `reference.csv` — monthly average fares for the backtest

Format:

```csv
label,month,avg_fare,source_note
DEL-BOM,2024-01-01,5200.00,DGCA Tariff Monitoring Unit
DEL-BOM,2024-02-01,5400.00,DGCA Tariff Monitoring Unit
```

When this file is present, `apix seed` loads it into `dgca_reference`.
When absent, the backtest in Phase 5 has no ground truth to compare against
and reports nothing — it does not silently fabricate a reference.

**Do not commit real DGCA data to a public repository without checking the
redistribution terms.** If you obtain real figures, keep them local and cite
the exact publication in `METHODOLOGY.md`.