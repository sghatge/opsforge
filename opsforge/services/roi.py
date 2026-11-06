"""OPSFORGE — ROI calculator.

Business Intelligence module: computes the *net* value of automating a
process. Deliberately conservative — implementation, maintenance, error
correction and human review costs are all part of the model.
"""

from __future__ import annotations

from ..db import Database

WORKING_WEEKS = 48


def calculate_roi(db: Database, data: dict) -> dict:
    try:
        hours_saved_week = float(data.get("hours_manual_per_week", 0))
        reduction_pct = float(data.get("reduction_pct", 0))
        hourly_cost = float(data.get("hourly_cost", 0))
        implementation_cost = float(data.get("implementation_cost", 0))
        maintenance_cost_year = float(data.get("maintenance_cost_year", 0))
        review_cost_year = float(data.get("review_cost_year", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"All inputs must be numeric: {exc}") from exc

    if hours_saved_week < 0 or reduction_pct < 0 or reduction_pct > 100:
        raise ValueError("hours_manual_per_week must be >= 0 and reduction_pct between 0 and 100.")

    hours_released_week = hours_saved_week * reduction_pct / 100
    hours_released_year = hours_released_week * WORKING_WEEKS
    gross_saving = hours_released_year * hourly_cost
    net_saving = gross_saving - implementation_cost - maintenance_cost_year - review_cost_year
    payback_months = (
        round(implementation_cost / (gross_saving / 12), 1)
        if gross_saving > 0 else None
    )

    result = {
        "process": data.get("process", "unnamed process"),
        "hours_released_per_week": round(hours_released_week, 1),
        "hours_released_per_year": round(hours_released_year, 1),
        "gross_annual_saving": round(gross_saving, 2),
        "implementation_cost": round(implementation_cost, 2),
        "annual_maintenance_cost": round(maintenance_cost_year, 2),
        "annual_review_cost": round(review_cost_year, 2),
        "net_first_year_value": round(net_saving, 2),
        "payback_months": payback_months,
        "assumptions": {
            "working_weeks_per_year": WORKING_WEEKS,
            "note": "Net value accounts for implementation, maintenance and review costs.",
        },
    }
    db.audit("roi.calculated", {"process": result["process"], "net_first_year_value": result["net_first_year_value"]})
    return result
