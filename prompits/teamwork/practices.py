"""
Practice definitions and helpers for `prompits.teamwork.practices`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Experimental notice: the teamwork practice surface is still under active development,
so new aliases and manager-mediated flows may continue to change.

Core types exposed here include `ControlManagerJobPractice`, `GetManagerJobPractice`,
`ListManagerDbTablesPractice`, `PostManagerJobResultPractice`, and
`PreviewManagerDbTablePractice`, which carry the main behavior or state managed by this
module.
"""

from __future__ import annotations

from typing import Any

from prompits.dispatcher.practices import (
    ControlDispatcherJobPractice,
    DispatcherPractice,
    GetDispatcherJobPractice,
    ListDispatcherDbTablesPractice,
    PostDispatcherJobResultPractice,
    PreviewDispatcherDbTablePractice,
    QueryDispatcherDbPractice,
    RegisterDispatcherWorkerPractice,
    ReportDispatcherJobPractice,
    SubmitDispatcherJobPractice,
)


class SubmitManagerJobPractice(SubmitDispatcherJobPractice):
    """Practice implementation for submit manager job workflows."""
    def __init__(self):
        """Initialize the submit manager job practice."""
        super().__init__()
        self.name = "Submit Manager Job"
        self.description = "Queue a job for manager workers."
        self.id = "manager-submit-job"
        self.tags = ["prompits", "teamwork", "manager", "queue"]


class RegisterManagerWorkerPractice(RegisterDispatcherWorkerPractice):
    """Practice implementation for register manager worker workflows."""
    def __init__(self):
        """Initialize the register manager worker practice."""
        super().__init__()
        self.name = "Register Manager Worker"
        self.description = "Upsert worker capabilities and heartbeat metadata for a manager queue."
        self.id = "manager-register-worker"
        self.tags = ["prompits", "teamwork", "manager", "workers"]


class HireWorkerManagerPractice(DispatcherPractice):
    """Practice implementation for worker hire workflows."""
    def __init__(self):
        """Initialize the worker hire manager practice."""
        super().__init__(
            name="Hire Worker Manager",
            description="Assign one manager to a waiting teamwork worker.",
            id="worker-hire-manager",
            tags=["prompits", "teamwork", "worker", "hire"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the worker hire manager practice."""
        if not self.agent or not hasattr(self.agent, "accept_manager_hire"):
            raise RuntimeError("Teamwork worker is not bound to this practice.")
        return self.agent.accept_manager_hire(**kwargs)


class GetManagerJobPractice(GetDispatcherJobPractice):
    """Practice implementation for get manager job workflows."""
    def __init__(self):
        """Initialize the get manager job practice."""
        super().__init__()
        self.name = "Get Manager Job"
        self.description = "Claim the next queued job from a manager."
        self.id = "manager-get-job"
        self.tags = ["prompits", "teamwork", "manager", "queue"]


class PostManagerJobResultPractice(PostDispatcherJobResultPractice):
    """Practice implementation for post manager job result workflows."""
    def __init__(self):
        """Initialize the post manager job result practice."""
        super().__init__()
        self.name = "Post Manager Job Result"
        self.description = "Accept a JobResult payload, persist outputs, and update manager state."
        self.id = "manager-post-job-result"
        self.tags = ["prompits", "teamwork", "manager", "results"]


class ControlManagerJobPractice(ControlDispatcherJobPractice):
    """Practice implementation for control manager job workflows."""
    def __init__(self):
        """Initialize the control manager job practice."""
        super().__init__()
        self.name = "Control Manager Job"
        self.description = "Pause, stop, resume, cancel, or delete a manager job."
        self.id = "manager-control-job"
        self.tags = ["prompits", "teamwork", "manager", "queue", "control"]


class ListManagerDbTablesPractice(ListDispatcherDbTablesPractice):
    """Practice implementation for list manager database tables workflows."""
    def __init__(self):
        """Initialize the list manager database tables practice."""
        super().__init__()
        self.name = "List Manager DB Tables"
        self.description = "List available tables in the manager database."
        self.id = "manager-db-list-tables"
        self.tags = ["prompits", "teamwork", "manager", "database", "read"]


class PreviewManagerDbTablePractice(PreviewDispatcherDbTablePractice):
    """Practice implementation for preview manager database table workflows."""
    def __init__(self):
        """Initialize the preview manager database table practice."""
        super().__init__()
        self.name = "Preview Manager DB Table"
        self.description = "Preview rows from one manager table."
        self.id = "manager-db-preview-table"
        self.tags = ["prompits", "teamwork", "manager", "database", "read"]


class QueryManagerDbPractice(QueryDispatcherDbPractice):
    """Practice implementation for query manager database workflows."""
    def __init__(self):
        """Initialize the query manager database practice."""
        super().__init__()
        self.name = "Query Manager DB"
        self.description = "Run a read-only SQL query against the manager database."
        self.id = "manager-db-query"
        self.tags = ["prompits", "teamwork", "manager", "database", "sql", "read"]


class ReportManagerJobPractice(ReportDispatcherJobPractice):
    """Practice implementation for report manager job workflows."""
    def __init__(self):
        """Initialize the report manager job practice."""
        super().__init__()
        self.name = "Report Manager Job"
        self.description = "Compatibility alias for PostManagerJobResult."
        self.id = "manager-report-job"
        self.tags = ["prompits", "teamwork", "manager", "results"]


__all__ = [
    "ControlManagerJobPractice",
    "GetManagerJobPractice",
    "HireWorkerManagerPractice",
    "ListManagerDbTablesPractice",
    "PostManagerJobResultPractice",
    "PreviewManagerDbTablePractice",
    "QueryManagerDbPractice",
    "RegisterManagerWorkerPractice",
    "ReportManagerJobPractice",
    "SubmitManagerJobPractice",
]
