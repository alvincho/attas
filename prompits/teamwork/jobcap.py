"""
Job-capability interfaces and adapters for `prompits.teamwork.jobcap`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

The file is intentionally lightweight, but its placement in the package makes it part of
the documented module surface.
"""

from prompits.dispatcher.jobcap import (
    CallableJobCap,
    JobCap,
    JobCapLoadResult,
    build_job_cap,
    coerce_environment_check_result,
    infer_job_cap_name,
    job_cap_entry_is_disabled,
    load_job_cap_map,
)

__all__ = [
    "CallableJobCap",
    "JobCap",
    "JobCapLoadResult",
    "build_job_cap",
    "coerce_environment_check_result",
    "infer_job_cap_name",
    "job_cap_entry_is_disabled",
    "load_job_cap_map",
]
