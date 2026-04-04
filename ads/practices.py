"""
Practice definitions and helpers for `ads.practices`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `ADSPractice`, `ControlAdsJobPractice`,
`GetAdsJobPractice`, `ListAdsDbTablesPractice`, and `PostAdsJobResultPractice`, which
carry the main behavior or state managed by this module.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from prompits.core.message import Message
from prompits.core.practice import Practice


class ADSPractice(Practice):
    """Practice implementation for ADS workflows."""
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


class SubmitAdsJobPractice(ADSPractice):
    """Practice implementation for submit ADS job workflows."""
    def __init__(self):
        """Initialize the submit ADS job practice."""
        super().__init__(
            name="Submit ADS Job",
            description="Queue a collection job for ADS workers.",
            id="ads-submit-job",
            tags=["ads", "dispatcher", "queue"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the submit ADS job practice."""
        if not self.agent or not hasattr(self.agent, "submit_job"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.submit_job(**kwargs)


class RegisterAdsWorkerPractice(ADSPractice):
    """Practice implementation for register ADS worker workflows."""
    def __init__(self):
        """Initialize the register ADS worker practice."""
        super().__init__(
            name="Register ADS Worker",
            description="Upsert worker capabilities and heartbeat metadata for the ADS queue.",
            id="ads-register-worker",
            tags=["ads", "dispatcher", "workers"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the register ADS worker practice."""
        if not self.agent or not hasattr(self.agent, "register_worker"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.register_worker(**kwargs)


class GetAdsJobPractice(ADSPractice):
    """Practice implementation for get ADS job workflows."""
    def __init__(self):
        """Initialize the get ADS job practice."""
        super().__init__(
            name="Get ADS Job",
            description="Claim the next queued ADS job and return it as a JobDetail payload.",
            id="ads-get-job",
            tags=["ads", "dispatcher", "queue"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the get ADS job practice."""
        if not self.agent or not hasattr(self.agent, "get_job"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.get_job(**kwargs)


class PostAdsJobResultPractice(ADSPractice):
    """Practice implementation for post ADS job result workflows."""
    def __init__(self):
        """Initialize the post ADS job result practice."""
        super().__init__(
            name="Post Job Result",
            description="Accept a JobResult payload, persist outputs, and update the ADS queue.",
            id="ads-post-job-result",
            tags=["ads", "dispatcher", "results"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the post ADS job result practice."""
        if not self.agent or not hasattr(self.agent, "post_job_result"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.post_job_result(**kwargs)


class ControlAdsJobPractice(ADSPractice):
    """Practice implementation for control ADS job workflows."""
    def __init__(self):
        """Initialize the control ADS job practice."""
        super().__init__(
            name="Control ADS Job",
            description="Pause or delete an ADS job from the dispatcher queue.",
            id="ads-control-job",
            tags=["ads", "dispatcher", "queue", "control"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the control ADS job practice."""
        if not self.agent or not hasattr(self.agent, "control_job"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.control_job(**kwargs)


class ListAdsDbTablesPractice(ADSPractice):
    """Practice implementation for list ADS database tables workflows."""
    def __init__(self):
        """Initialize the list ADS database tables practice."""
        super().__init__(
            name="List ADS DB Tables",
            description="List available tables in the ADS dispatcher database.",
            id="ads-db-list-tables",
            tags=["ads", "dispatcher", "database", "read"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the list ADS database tables practice."""
        if not self.agent or not hasattr(self.agent, "list_db_tables"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.list_db_tables(**kwargs)


class PreviewAdsDbTablePractice(ADSPractice):
    """Practice implementation for preview ADS database table workflows."""
    def __init__(self):
        """Initialize the preview ADS database table practice."""
        super().__init__(
            name="Preview ADS DB Table",
            description="Preview rows from one ADS dispatcher table.",
            id="ads-db-preview-table",
            tags=["ads", "dispatcher", "database", "read"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the preview ADS database table practice."""
        if not self.agent or not hasattr(self.agent, "preview_db_table"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.preview_db_table(**kwargs)


class QueryAdsDbPractice(ADSPractice):
    """Practice implementation for query ADS database workflows."""
    def __init__(self):
        """Initialize the query ADS database practice."""
        super().__init__(
            name="Query ADS DB",
            description="Run a read-only SQL query against the ADS dispatcher database.",
            id="ads-db-query",
            tags=["ads", "dispatcher", "database", "sql", "read"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def execute(self, **kwargs) -> Any:
        """Handle execute for the query ADS database practice."""
        if not self.agent or not hasattr(self.agent, "query_db"):
            raise RuntimeError("ADS dispatcher is not bound to this practice.")
        return self.agent.query_db(**kwargs)


class ReportAdsJobPractice(PostAdsJobResultPractice):
    """Practice implementation for report ADS job workflows."""
    def __init__(self):
        """Initialize the report ADS job practice."""
        super().__init__()
        self.name = "Report ADS Job"
        self.description = "Compatibility alias for PostJobResult."
        self.id = "ads-report-job"
