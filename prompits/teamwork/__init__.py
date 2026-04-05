"""
Public package exports for `prompits.teamwork`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Experimental notice: `prompits.teamwork` is still under active development. Expect
some API, config, and orchestration details to change while the package is being
stabilized.

It re-exports symbols such as `CallableJobCap`, `DispatcherManagerAgent`, `JobCap`,
`JobDetail`, and `JobResult` so callers can import the package through a stable surface.
"""

from prompits.teamwork.agents import DispatcherManagerAgent, TeamManagerAgent, TeamWorkerAgent
from prompits.teamwork.boss import TeamBossAgent
from prompits.teamwork.jobcap import CallableJobCap, JobCap, build_job_cap, load_job_cap_map
from prompits.teamwork.models import (
    JobDetail,
    JobResult,
    ManagedExecutionState,
    ManagedManagerAssignment,
    ManagedResultSummary,
    ManagedScheduleRequest,
    ManagedScheduleState,
    ManagedTicketRef,
    ManagedTicketRequest,
    ManagedWorkItem,
    ManagedWorkSchedule,
    ManagedWorkTicket,
    ManagedWorkerAssignment,
    TeamWorkerHireState,
)

__all__ = [
    "CallableJobCap",
    "DispatcherManagerAgent",
    "JobCap",
    "JobDetail",
    "JobResult",
    "ManagedExecutionState",
    "ManagedManagerAssignment",
    "ManagedResultSummary",
    "ManagedScheduleRequest",
    "ManagedScheduleState",
    "ManagedTicketRef",
    "ManagedTicketRequest",
    "ManagedWorkItem",
    "ManagedWorkSchedule",
    "ManagedWorkTicket",
    "ManagedWorkerAssignment",
    "TeamWorkerHireState",
    "TeamBossAgent",
    "TeamManagerAgent",
    "TeamWorkerAgent",
    "build_job_cap",
    "load_job_cap_map",
]
