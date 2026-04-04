"""
Public package exports for `prompits.teamwork`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

It re-exports symbols such as `CallableJobCap`, `DispatcherManagerAgent`, `JobCap`,
`JobDetail`, and `JobResult` so callers can import the package through a stable surface.
"""

from prompits.teamwork.agents import DispatcherManagerAgent, TeamManagerAgent, TeamWorkerAgent
from prompits.teamwork.boss import TeamBossAgent
from prompits.teamwork.jobcap import CallableJobCap, JobCap, build_job_cap, load_job_cap_map
from prompits.teamwork.models import JobDetail, JobResult

__all__ = [
    "CallableJobCap",
    "DispatcherManagerAgent",
    "JobCap",
    "JobDetail",
    "JobResult",
    "TeamBossAgent",
    "TeamManagerAgent",
    "TeamWorkerAgent",
    "build_job_cap",
    "load_job_cap_map",
]
