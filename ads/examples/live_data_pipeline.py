"""
Live data-pipeline helpers for `ads.examples.live_data_pipeline`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace. This module adapts the real ADS collectors
to the simplified public SQLite demo so the demo job names can stay compact while
still fetching live data.
"""

from __future__ import annotations

from typing import Any

from ads.jobcap import JobCap, coerce_environment_check_result
from ads.models import JobDetail, JobResult
from ads.schema import TABLE_FINANCIAL_STATEMENTS, TABLE_FUNDAMENTALS
from ads.sec import USFilingBulkJobCap, USFilingMappingJobCap


class LiveSECPipelineJobCap(JobCap):
    """Compose the live SEC bulk + mapping pipeline behind one demo job."""

    def __init__(
        self,
        name: str,
        *,
        primary_target: str = TABLE_FUNDAMENTALS,
        provider: str = "sec_edgar",
        dispatcher_address: str = "",
        cache_dir: str = "",
        cache_max_age_hours: float = 24.0,
        timeout_sec: float = 120.0,
        user_agent: str = "",
        bulk_job_cap: JobCap | None = None,
        mapping_job_cap: JobCap | None = None,
        source: str = "",
    ):
        """Initialize the live SEC pipeline job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        normalized_primary_target = str(primary_target or "").strip()
        if normalized_primary_target not in {TABLE_FUNDAMENTALS, TABLE_FINANCIAL_STATEMENTS}:
            raise ValueError(
                "primary_target must be one of "
                f"'{TABLE_FUNDAMENTALS}' or '{TABLE_FINANCIAL_STATEMENTS}'."
            )
        self.primary_target = normalized_primary_target

        if bulk_job_cap is None:
            bulk_kwargs: dict[str, Any] = {
                "name": f"{self.name} sec bulk refresh",
                "provider": provider,
                "timeout_sec": timeout_sec,
                "source": self.source,
            }
            if cache_dir:
                bulk_kwargs["cache_dir"] = cache_dir
            if cache_max_age_hours not in (None, ""):
                bulk_kwargs["cache_max_age_hours"] = cache_max_age_hours
            if user_agent:
                bulk_kwargs["user_agent"] = user_agent
            bulk_job_cap = USFilingBulkJobCap(**bulk_kwargs)
        if mapping_job_cap is None:
            mapping_job_cap = USFilingMappingJobCap(
                name=f"{self.name} sec mapping",
                provider=provider,
                dispatcher_address=dispatcher_address,
                source=self.source,
            )

        self.bulk_job_cap = bulk_job_cap
        self.mapping_job_cap = mapping_job_cap

    def bind_worker(self, worker: Any) -> "LiveSECPipelineJobCap":
        """Bind the worker to the composite and nested job caps."""
        super().bind_worker(worker)
        for capability in (self.bulk_job_cap, self.mapping_job_cap):
            bind_worker = getattr(capability, "bind_worker", None)
            if callable(bind_worker):
                bind_worker(worker)
        return self

    def check_environment(self) -> tuple[bool, str]:
        """Check the environment for the composed live SEC pipeline."""
        for capability in (self.bulk_job_cap, self.mapping_job_cap):
            available, reason = coerce_environment_check_result(capability.check_environment())
            if not available:
                return False, reason or f"{capability.name} is unavailable."
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Run the live SEC bulk refresh and company mapping."""
        bulk_result = JobResult.from_value(self.bulk_job_cap(job))
        bulk_status = str(bulk_result.status or "completed").strip().lower() or "completed"
        if bulk_status != "completed":
            return bulk_result.model_copy(update={"job_id": job.id})

        mapping_result = JobResult.from_value(self.mapping_job_cap(job))
        remapped_result = self._remap_primary_target(mapping_result)
        combined_summary = dict(remapped_result.result_summary or {})
        combined_summary["bulk_refresh"] = dict(bulk_result.result_summary or {})
        return remapped_result.model_copy(
            update={
                "job_id": job.id,
                "raw_payload": {
                    "bulk_refresh": bulk_result.raw_payload,
                    "mapping": remapped_result.raw_payload,
                },
                "result_summary": combined_summary,
            }
        )

    def _remap_primary_target(self, result: JobResult) -> JobResult:
        """Return the job result with the requested primary target first."""
        if self.primary_target == TABLE_FUNDAMENTALS:
            return result

        primary_rows = []
        additional_targets = []
        for target in list(result.additional_targets or []):
            table_name = str(target.get("table_name") or "").strip()
            if table_name == TABLE_FINANCIAL_STATEMENTS:
                primary_rows.extend(list(target.get("rows") or []))
                continue
            additional_targets.append(dict(target))
        if result.collected_rows:
            additional_targets.insert(
                0,
                {
                    "table_name": TABLE_FUNDAMENTALS,
                    "rows": list(result.collected_rows),
                },
            )
        return result.model_copy(
            update={
                "target_table": TABLE_FINANCIAL_STATEMENTS,
                "collected_rows": primary_rows,
                "additional_targets": additional_targets,
            }
        )


class LiveSECFundamentalsJobCap(LiveSECPipelineJobCap):
    """Live SEC fundamentals demo job cap."""

    def __init__(self, name: str = "fundamentals", **kwargs: Any):
        """Initialize the live SEC fundamentals demo job cap."""
        super().__init__(name=name, primary_target=TABLE_FUNDAMENTALS, **kwargs)


class LiveSECFinancialStatementsJobCap(LiveSECPipelineJobCap):
    """Live SEC financial statements demo job cap."""

    def __init__(self, name: str = "financial_statements", **kwargs: Any):
        """Initialize the live SEC financial statements demo job cap."""
        super().__init__(name=name, primary_target=TABLE_FINANCIAL_STATEMENTS, **kwargs)
