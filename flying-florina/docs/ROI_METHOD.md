# ROI method (assumption-driven, editable)

Implemented in `backend/app/simulation/engine.py::roi`, exposed at `POST /api/simulations/roi`, editable in the Executive Value Studio.

```
labor          = manual_hours_per_month x 12 x loaded_labor_cost_per_hour x automation_fraction
downtime       = unscheduled_downtime_hours_per_year x downtime_reduction x downtime_cost_per_hour
benefit        = labor + downtime + avoided_rework_per_year
first_year_cost = pilot_engineering_cost + annual_run_cost + incremental_software_license_cost
payback_months = pilot_engineering_cost / ((benefit - annual_run_cost) / 12)
```

| Input | Default | Source |
|---|---|---|
| manual_hours_per_month | 320 | assumption (reconciliation + evidence assembly) |
| loaded_labor_cost_per_hour | $95 | assumption |
| automation_fraction | 15%–35% | assumption range |
| unscheduled_downtime_hours_per_year | from synthetic data (trailing 12 months) | `maintenance_events` |
| downtime_reduction | 1%–4% | assumption range |
| downtime_cost_per_hour | $6,500 | fictional planning assumption |
| avoided_rework_per_year | $40,000 | assumption |
| pilot_engineering_cost | 2 eng x 13 wk x 40 h x $120 | assumption |
| annual_run_cost | $60,000 | support, hardware share, security review |
| incremental_software_license_cost | $0 | open-source stack |

The output is a **range**, never a single promised number. Replace every assumption with pilot measurements
before showing figures to a decision maker. The delay-scenario model (`compare_delays`) documents its own formulas,
assumptions and seeded Monte Carlo method in every response.
