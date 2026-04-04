"""
Job-capability interfaces and adapters for `prompits.dispatcher.jobcap`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Key definitions include `CallableJobCap`, `JobCap`, `JobCapLoadResult`, `build_job_cap`,
and `build_job_cap_map`, which provide the main entry points used by neighboring modules
and tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import import_module, util as importlib_util
from typing import Any, Callable, Dict, Iterable, Mapping
from urllib.parse import urlparse

from prompits.dispatcher.models import JobDetail


JobCallable = Callable[[JobDetail], Any]


def _import_reference(reference: str) -> Any:
    """Internal helper for import reference."""
    ref = str(reference or "").strip()
    if not ref:
        raise ValueError("Job capability reference is required.")
    if ":" in ref:
        module_name, attr_name = ref.split(":", 1)
    else:
        module_name, _, attr_name = ref.rpartition(".")
    if not module_name or not attr_name:
        raise ValueError(f"Invalid job capability reference: {reference}")
    module = import_module(module_name)
    return getattr(module, attr_name)


def _import_callable(reference: str) -> JobCallable:
    """Internal helper for import callable."""
    target = _import_reference(reference)
    if not callable(target):
        raise TypeError(f"Configured job capability '{reference}' is not callable.")
    return target


def _reference_name(reference: str) -> str:
    """Internal helper to return the reference name."""
    return str(reference or "").strip().split(":")[-1].split(".")[-1]


def _normalize_job_cap_name(value: Any) -> str:
    """Internal helper to normalize the job cap name."""
    return str(value or "").strip().lower()


def infer_job_cap_name(entry: Mapping[str, Any] | "JobCap" | str) -> str:
    """Return the infer job cap name."""
    if isinstance(entry, JobCap):
        return entry.name
    if isinstance(entry, str):
        return _normalize_job_cap_name(_reference_name(entry))
    if not isinstance(entry, Mapping):
        return ""

    explicit_name = _normalize_job_cap_name(entry.get("name") or entry.get("capability"))
    if explicit_name:
        return explicit_name

    type_value = entry.get("type") or entry.get("class") or entry.get("job_cap_type")
    if isinstance(type_value, str) and type_value.strip():
        return _normalize_job_cap_name(_reference_name(type_value))

    fn_value = entry.get("fn") or entry.get("callable") or entry.get("handler") or entry.get("function")
    if isinstance(fn_value, str):
        return _normalize_job_cap_name(_reference_name(fn_value))
    if callable(fn_value):
        return _normalize_job_cap_name(getattr(fn_value, "__name__", "job_cap"))
    return ""


def _normalize_job_cap_entries(
    entries: Iterable[Mapping[str, Any] | "JobCap" | str] | Mapping[str, Any] | None,
) -> list[Mapping[str, Any] | "JobCap" | str]:
    """Internal helper to normalize the job cap entries."""
    if isinstance(entries, Mapping):
        iterable: list[Mapping[str, Any] | JobCap | str] = []
        for key, value in entries.items():
            if isinstance(value, Mapping):
                merged = dict(value)
                merged.setdefault("name", str(key))
                iterable.append(merged)
            else:
                iterable.append({"name": str(key), "callable": value})
        return iterable
    return list(entries or [])


def _coerce_config_bool(value: Any) -> bool:
    """Internal helper to coerce the config bool."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return bool(value)


def job_cap_entry_is_disabled(entry: Any) -> bool:
    """Handle job cap entry is disabled."""
    if not isinstance(entry, Mapping):
        return False
    return _coerce_config_bool(entry.get("disabled"))


def coerce_environment_check_result(result: Any) -> tuple[bool, str]:
    """Coerce the environment check result."""
    if isinstance(result, tuple):
        available = bool(result[0]) if result else False
        reason = str(result[1] or "").strip() if len(result) > 1 else ""
        return available, reason
    return bool(result), ""


@dataclass
class JobCapLoadResult:
    """Represent a job cap load result."""
    capabilities: Dict[str, "JobCap"]
    unavailable: Dict[str, str]


class JobCap(ABC):
    """Job capability implementation for value workflows."""
    def __init__(self, name: str, fn: JobCallable | None = None, *, source: str = ""):
        """Initialize the job cap."""
        normalized_name = str(name or "").strip().lower()
        if not normalized_name:
            raise ValueError("Job capability name is required.")
        resolved_fn = fn or self.finish
        if not callable(resolved_fn):
            raise TypeError("Job capability function must be callable.")
        self.name = normalized_name
        self.fn = resolved_fn
        self.source = str(source or "")
        self.worker = None

    @abstractmethod
    def finish(self, job: JobDetail) -> Any:
        """Handle finish for the job cap."""
        raise NotImplementedError

    def __call__(self, job: JobDetail) -> Any:
        """Invoke the instance like a callable."""
        return self.finish(job)

    def check_environment(self) -> bool | tuple[bool, str]:
        """Handle check environment for the job cap."""
        return True, ""

    def to_metadata(self) -> Dict[str, Any]:
        """Convert the value to metadata."""
        return {
            "name": self.name,
            "callable": self.source or getattr(self.fn, "__name__", ""),
        }

    def bind_worker(self, worker: Any) -> "JobCap":
        """Bind the worker."""
        self.worker = worker
        return self

    @staticmethod
    def check_module_available(module_name: str) -> tuple[bool, str]:
        """Handle check module available for the job cap."""
        normalized_name = str(module_name or "").strip()
        if not normalized_name:
            return False, "module name is required."
        if importlib_util.find_spec(normalized_name) is None:
            return False, f"Python module '{normalized_name}' is not installed."
        return True, ""

    @staticmethod
    def check_url_configured(url: Any, *, label: str = "URL") -> tuple[bool, str]:
        """Handle check URL configured for the job cap."""
        normalized_url = str(url or "").strip()
        if not normalized_url:
            return False, f"{label} is not configured."
        parsed = urlparse(normalized_url)
        if parsed.scheme not in {"http", "https", "ftp"} or not parsed.netloc:
            return False, f"{label} '{normalized_url}' is not a valid URL."
        return True, ""

    @staticmethod
    def check_url_reachable(
        url: Any,
        *,
        request_get: Callable[..., Any] | None,
        timeout_sec: float = 5.0,
        headers: Mapping[str, Any] | None = None,
        label: str = "URL",
    ) -> tuple[bool, str]:
        """Handle check URL reachable for the job cap."""
        configured, reason = JobCap.check_url_configured(url, label=label)
        if not configured:
            return False, reason
        if not callable(request_get):
            return False, f"{label} probe requires a callable request_get."

        normalized_url = str(url or "").strip()
        request_kwargs = {"timeout": max(float(timeout_sec or 0.0), 0.1)}
        if headers:
            request_kwargs["headers"] = dict(headers)

        try:
            response = request_get(normalized_url, **request_kwargs)
        except Exception as exc:
            return False, f"{label} probe failed for '{normalized_url}': {exc}"

        status_code = int(getattr(response, "status_code", 200) or 200)
        if status_code >= 400:
            return False, f"{label} probe returned status {status_code} for '{normalized_url}'."
        return True, ""


class CallableJobCap(JobCap):
    """Job capability implementation for callable workflows."""
    def finish(self, job: JobDetail) -> Any:
        """Handle finish for the callable job cap."""
        return self.fn(job)


def _import_job_cap_type(reference: str) -> type[JobCap]:
    """Internal helper for import job cap type."""
    target = _import_reference(reference)
    if not isinstance(target, type) or not issubclass(target, JobCap):
        raise TypeError(f"Configured job capability '{reference}' is not a JobCap type.")
    return target


def build_job_cap(entry: Mapping[str, Any] | JobCap | str) -> JobCap:
    """Build the job cap."""
    if isinstance(entry, JobCap):
        return entry
    if isinstance(entry, str):
        fn = _import_callable(entry)
        inferred_name = _reference_name(entry)
        return CallableJobCap(name=inferred_name, fn=fn, source=entry)
    if not isinstance(entry, Mapping):
        raise TypeError(f"Unsupported job capability config: {type(entry).__name__}")

    name = str(entry.get("name") or entry.get("capability") or "").strip().lower()
    type_value = entry.get("type") or entry.get("class") or entry.get("job_cap_type")
    if isinstance(type_value, str) and type_value.strip():
        cap_type = _import_job_cap_type(type_value)
        kwargs = {
            key: value
            for key, value in entry.items()
            if key not in {"name", "capability", "type", "class", "job_cap_type", "disabled"}
        }
        kwargs.setdefault("name", name or getattr(cap_type, "__name__", "job_cap"))
        kwargs.setdefault("source", type_value)
        return cap_type(**kwargs)

    fn_value = entry.get("fn") or entry.get("callable") or entry.get("handler") or entry.get("function")
    if isinstance(fn_value, str):
        fn = _import_callable(fn_value)
        return CallableJobCap(name=name or fn.__name__, fn=fn, source=fn_value)
    if callable(fn_value):
        return CallableJobCap(name=name or getattr(fn_value, "__name__", "job_cap"), fn=fn_value)
    raise ValueError(f"Job capability '{name or entry}' is missing a callable function.")


def load_job_cap_map(
    entries: Iterable[Mapping[str, Any] | JobCap | str] | Mapping[str, Any] | None,
) -> JobCapLoadResult:
    """Load the job cap map."""
    capability_map: Dict[str, JobCap] = {}
    unavailable: Dict[str, str] = {}
    for entry in _normalize_job_cap_entries(entries):
        inferred_name = infer_job_cap_name(entry) or "job_cap"
        if job_cap_entry_is_disabled(entry):
            unavailable[inferred_name] = "disabled by config."
            continue
        capability = build_job_cap(entry)
        available, reason = coerce_environment_check_result(capability.check_environment())
        if available:
            capability_map[capability.name] = capability
            continue
        capability_name = capability.name or inferred_name
        unavailable[capability_name] = reason or "environment check failed."
    return JobCapLoadResult(capabilities=capability_map, unavailable=unavailable)


def build_job_cap_map(
    entries: Iterable[Mapping[str, Any] | JobCap | str] | Mapping[str, Any] | None,
) -> Dict[str, JobCap]:
    """Build the job cap map."""
    return load_job_cap_map(entries).capabilities
