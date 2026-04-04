"""
Public package exports for `prompits.dispatcher`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

It re-exports symbols such as `CallableJobCap`, `DispatcherAgent`,
`DispatcherBossAgent`, `DispatcherWorkerAgent`, and `JobCap` so callers can import the
package through a stable surface.
"""

from prompits.dispatcher.agents import DispatcherAgent, DispatcherWorkerAgent
from prompits.dispatcher.boss import DispatcherBossAgent
from prompits.dispatcher.jobcap import CallableJobCap, JobCap
from prompits.dispatcher.models import JobDetail, JobResult

__all__ = [
    "CallableJobCap",
    "DispatcherAgent",
    "DispatcherBossAgent",
    "DispatcherWorkerAgent",
    "JobCap",
    "JobDetail",
    "JobResult",
]
