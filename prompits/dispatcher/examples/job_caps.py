"""
Job Caps module for `prompits.dispatcher.examples.job_caps`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Important callables in this file include `echo_job_cap`, which capture the primary
workflow implemented by the module.
"""

from __future__ import annotations

from typing import Any

from prompits.dispatcher.models import JobDetail, JobResult


def echo_job_cap(job: JobDetail) -> JobResult:
    """Handle echo job cap."""
    payload = dict(job.payload or {}) if isinstance(job.payload, dict) else {"value": job.payload}
    target = ""
    if job.targets:
        target = str(job.targets[0] or "").strip()
    elif isinstance(payload, dict):
        target = str(payload.get("target") or "").strip()

    row: dict[str, Any] = {
        "message": str(payload.get("message") or "echo"),
        "target": target,
        "job_id": job.id,
    }
    return JobResult(
        job_id=job.id,
        status="completed",
        target_table="dispatcher_echo_output",
        collected_rows=[row],
        raw_payload={"echoed": row},
        result_summary={"rows": 1},
    )
