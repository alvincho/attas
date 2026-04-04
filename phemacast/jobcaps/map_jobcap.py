"""
Map Jobcap module for `phemacast.jobcaps.map_jobcap`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the jobcaps package exposes reusable job
capability wrappers for map and casting workflows.

Core types exposed here include `RunMapJobCap`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from phemacast.castrs.map_castr import MapCastr
from prompits.dispatcher.jobcap import JobCap
from prompits.dispatcher.models import JobDetail, JobResult


class RunMapJobCap(JobCap):
    """Dispatcher capability that runs MapCastr for a MapPhemar-generated Phema."""

    def __init__(
        self,
        name: str = "run map",
        *,
        castr_config: Mapping[str, Any] | None = None,
        castr_config_path: str = "",
        target_table: str = "dispatcher_map_runs",
        timeout_sec: float = 30.0,
        request_post: Any = None,
        source: str = "",
    ):
        """Initialize the run map job cap."""
        super().__init__(name=name, source=source or "phemacast.jobcaps.map_jobcap:RunMapJobCap")
        self.castr_config = dict(castr_config or {}) if isinstance(castr_config, Mapping) else {}
        self.castr_config_path = str(castr_config_path or "").strip()
        self.target_table = str(target_table or "").strip()
        self.timeout_sec = timeout_sec
        self.request_post = request_post
        self._castr: Optional[MapCastr] = None

    def _castr_instance(self) -> MapCastr:
        """Internal helper for castr instance."""
        if self._castr is not None:
            return self._castr
        if self.castr_config_path:
            self._castr = MapCastr.from_config(
                self.castr_config_path,
                auto_register=False,
                request_post=self.request_post,
                timeout_sec=self.timeout_sec,
            )
            return self._castr
        if self.castr_config:
            self._castr = MapCastr.from_config(
                self.castr_config,
                auto_register=False,
                request_post=self.request_post,
                timeout_sec=self.timeout_sec,
            )
            return self._castr
        worker_pool = getattr(self.worker, "pool", None)
        self._castr = MapCastr(
            name="MapCastr",
            pool=worker_pool,
            auto_register=False,
            request_post=self.request_post,
            timeout_sec=self.timeout_sec,
        )
        return self._castr

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the run map job cap."""
        payload = dict(job.payload or {}) if isinstance(job.payload, Mapping) else {}
        phema = payload.get("phema")
        if not isinstance(phema, Mapping):
            raise ValueError("RunMapJobCap requires payload.phema.")

        preferences = dict(payload.get("preferences") or {}) if isinstance(payload.get("preferences"), Mapping) else {}
        if "input" not in preferences:
            for key in ("input", "params", "initial_input"):
                if key in payload:
                    preferences["input"] = payload.get(key)
                    break
        if "extra_parameters" not in preferences:
            for key in ("extra_parameters", "extra_params"):
                if isinstance(payload.get(key), Mapping):
                    preferences["extra_parameters"] = dict(payload.get(key) or {})
                    break
        if "node_parameters" not in preferences:
            for key in ("node_parameters", "node_params"):
                if isinstance(payload.get(key), Mapping):
                    preferences["node_parameters"] = dict(payload.get(key) or {})
                    break
        if "plaza_url" not in preferences:
            for key in ("plaza_url", "plazaUrl"):
                value = str(payload.get(key) or "").strip()
                if value:
                    preferences["plaza_url"] = value
                    break

        target_format = str(payload.get("format") or payload.get("media_type") or "JSON").strip() or "JSON"
        cast_result = self._castr_instance().cast(dict(phema), format=target_format, preferences=preferences)
        steps = cast_result.get("steps") if isinstance(cast_result.get("steps"), list) else []
        execution = dict(cast_result.get("execution") or {}) if isinstance(cast_result.get("execution"), Mapping) else {}
        summary_row: Dict[str, Any] = {
            "job_id": job.id,
            "phema_id": str(execution.get("phema_id") or phema.get("phema_id") or phema.get("id") or ""),
            "phema_name": str(execution.get("phema_name") or phema.get("name") or ""),
            "format": str(cast_result.get("format") or target_format),
            "location": str(cast_result.get("location") or ""),
            "url": str(cast_result.get("url") or ""),
            "step_count": len(steps),
            "result": cast_result.get("result"),
        }
        return JobResult(
            job_id=job.id,
            status="completed",
            collected_rows=[summary_row],
            raw_payload=cast_result,
            result_summary={
                "rows": 1,
                "steps": len(steps),
                "location": str(cast_result.get("location") or ""),
                "format": str(cast_result.get("format") or target_format),
            },
            target_table=str(payload.get("target_table") or self.target_table or ""),
        )


__all__ = ["RunMapJobCap"]
