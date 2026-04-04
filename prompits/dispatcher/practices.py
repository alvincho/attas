"""
Practice definitions and helpers for `prompits.dispatcher.practices`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Core types exposed here include `ControlDispatcherJobPractice`, `DispatcherPractice`,
`GetDispatcherJobPractice`, `ListDispatcherDbTablesPractice`, and
`PostDispatcherJobResultPractice`, which carry the main behavior or state managed by
this module.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from prompits.core.message import Message
from prompits.core.practice import Practice


class DispatcherPractice(Practice):
    """Practice implementation for dispatcher workflows."""
    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post(self.path)
        async def invoke(message: Message):
            """Route handler for POST requests."""
            content = message.content
            try:
                if isinstance(content, dict):
                    return await run_in_threadpool(self.execute, **content)
                if content is None:
                    return await run_in_threadpool(self.execute)
                return await run_in_threadpool(self.execute, content=content)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        app.include_router(router)


class SubmitDispatcherJobPractice(DispatcherPractice):
    """Practice implementation for submit dispatcher job workflows."""
    def __init__(self):
        """Initialize the submit dispatcher job practice."""
        super().__init__(
            name="Submit Dispatcher Job",
            description="Queue a job for dispatcher workers.",
            id="dispatcher-submit-job",
            tags=["prompits", "dispatcher", "queue"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the submit dispatcher job practice."""
        if not self.agent or not hasattr(self.agent, "submit_job"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.submit_job(**kwargs)


class RegisterDispatcherWorkerPractice(DispatcherPractice):
    """Practice implementation for register dispatcher worker workflows."""
    def __init__(self):
        """Initialize the register dispatcher worker practice."""
        super().__init__(
            name="Register Dispatcher Worker",
            description="Upsert worker capabilities and heartbeat metadata for the queue.",
            id="dispatcher-register-worker",
            tags=["prompits", "dispatcher", "workers"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the register dispatcher worker practice."""
        if not self.agent or not hasattr(self.agent, "register_worker"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.register_worker(**kwargs)


class GetDispatcherJobPractice(DispatcherPractice):
    """Practice implementation for get dispatcher job workflows."""
    def __init__(self):
        """Initialize the get dispatcher job practice."""
        super().__init__(
            name="Get Dispatcher Job",
            description="Claim the next queued job and return it as a JobDetail payload.",
            id="dispatcher-get-job",
            tags=["prompits", "dispatcher", "queue"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the get dispatcher job practice."""
        if not self.agent or not hasattr(self.agent, "get_job"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.get_job(**kwargs)


class PostDispatcherJobResultPractice(DispatcherPractice):
    """Practice implementation for post dispatcher job result workflows."""
    def __init__(self):
        """Initialize the post dispatcher job result practice."""
        super().__init__(
            name="Post Dispatcher Job Result",
            description="Accept a JobResult payload, persist outputs, and update the queue.",
            id="dispatcher-post-job-result",
            tags=["prompits", "dispatcher", "results"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the post dispatcher job result practice."""
        if not self.agent or not hasattr(self.agent, "post_job_result"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.post_job_result(**kwargs)


class ControlDispatcherJobPractice(DispatcherPractice):
    """Practice implementation for control dispatcher job workflows."""
    def __init__(self):
        """Initialize the control dispatcher job practice."""
        super().__init__(
            name="Control Dispatcher Job",
            description="Pause, stop, resume, cancel, or delete a queued job.",
            id="dispatcher-control-job",
            tags=["prompits", "dispatcher", "queue", "control"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the control dispatcher job practice."""
        if not self.agent or not hasattr(self.agent, "control_job"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.control_job(**kwargs)


class ListDispatcherDbTablesPractice(DispatcherPractice):
    """Practice implementation for list dispatcher database tables workflows."""
    def __init__(self):
        """Initialize the list dispatcher database tables practice."""
        super().__init__(
            name="List Dispatcher DB Tables",
            description="List available tables in the dispatcher database.",
            id="dispatcher-db-list-tables",
            tags=["prompits", "dispatcher", "database", "read"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the list dispatcher database tables practice."""
        if not self.agent or not hasattr(self.agent, "list_db_tables"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.list_db_tables(**kwargs)


class PreviewDispatcherDbTablePractice(DispatcherPractice):
    """Practice implementation for preview dispatcher database table workflows."""
    def __init__(self):
        """Initialize the preview dispatcher database table practice."""
        super().__init__(
            name="Preview Dispatcher DB Table",
            description="Preview rows from one dispatcher table.",
            id="dispatcher-db-preview-table",
            tags=["prompits", "dispatcher", "database", "read"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the preview dispatcher database table practice."""
        if not self.agent or not hasattr(self.agent, "preview_db_table"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.preview_db_table(**kwargs)


class QueryDispatcherDbPractice(DispatcherPractice):
    """Practice implementation for query dispatcher database workflows."""
    def __init__(self):
        """Initialize the query dispatcher database practice."""
        super().__init__(
            name="Query Dispatcher DB",
            description="Run a read-only SQL query against the dispatcher database.",
            id="dispatcher-db-query",
            tags=["prompits", "dispatcher", "database", "sql", "read"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the query dispatcher database practice."""
        if not self.agent or not hasattr(self.agent, "query_db"):
            raise RuntimeError("Dispatcher agent is not bound to this practice.")
        return self.agent.query_db(**kwargs)


class ReportDispatcherJobPractice(PostDispatcherJobResultPractice):
    """Practice implementation for report dispatcher job workflows."""
    def __init__(self):
        """Initialize the report dispatcher job practice."""
        super().__init__()
        self.name = "Report Dispatcher Job"
        self.description = "Compatibility alias for PostDispatcherJobResult."
        self.id = "dispatcher-report-job"
