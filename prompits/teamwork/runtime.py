"""
Runtime helpers for `prompits.teamwork.runtime`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Important callables in this file include `read_teamwork_config` and
`normalize_teamwork_config`, which capture the primary workflow implemented by the
module.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from prompits.dispatcher.runtime import (
    ConfigInput,
    build_dispatch_job,
    build_id,
    build_raw_payload_row,
    build_result_row,
    build_worker_history_entry,
    build_worker_registration,
    coerce_job_detail,
    coerce_job_result,
    coerce_json_object,
    coerce_json_payload,
    coerce_record_list,
    job_is_ready,
    job_matches_capabilities,
    job_sort_key,
    normalize_capabilities,
    normalize_string_list,
    normalize_target,
    parse_datetime_value,
    prepare_table_records,
    read_dispatcher_config,
    utcnow_iso,
)


def read_teamwork_config(config: ConfigInput) -> Dict[str, Any]:
    """Read the teamwork config."""
    return read_dispatcher_config(config)


def normalize_teamwork_config(config: ConfigInput, *, role: str = "") -> Dict[str, Any]:
    """Normalize the teamwork config."""
    loaded = read_teamwork_config(config)
    normalized = dict(loaded or {})

    teamwork_settings = loaded.get("teamwork") if isinstance(loaded.get("teamwork"), Mapping) else {}
    dispatcher_settings = loaded.get("dispatcher") if isinstance(loaded.get("dispatcher"), Mapping) else {}
    role_settings = loaded.get(role) if role and isinstance(loaded.get(role), Mapping) else {}
    manager_settings = loaded.get("manager") if isinstance(loaded.get("manager"), Mapping) else {}

    merged_settings: Dict[str, Any] = {}
    for source in (teamwork_settings, dispatcher_settings, role_settings):
        if isinstance(source, Mapping):
            merged_settings.update(dict(source))
    normalized["dispatcher"] = merged_settings

    address_candidates = (
        merged_settings.get("manager_address"),
        merged_settings.get("dispatcher_address"),
        merged_settings.get("upstream_manager_address"),
        manager_settings.get("manager_address"),
        manager_settings.get("dispatcher_address"),
        loaded.get("manager_address"),
        loaded.get("dispatcher_address"),
    )
    dispatcher_address = next((str(value or "").strip() for value in address_candidates if str(value or "").strip()), "")
    if dispatcher_address:
        normalized["dispatcher_address"] = dispatcher_address

    party_candidates = (
        merged_settings.get("manager_party"),
        merged_settings.get("dispatcher_party"),
        merged_settings.get("upstream_manager_party"),
        manager_settings.get("manager_party"),
        manager_settings.get("dispatcher_party"),
        loaded.get("manager_party"),
        loaded.get("dispatcher_party"),
        loaded.get("party"),
    )
    dispatcher_party = next((str(value or "").strip() for value in party_candidates if str(value or "").strip()), "")
    if dispatcher_party:
        normalized["dispatcher_party"] = dispatcher_party

    return normalized


__all__ = [
    "ConfigInput",
    "build_dispatch_job",
    "build_id",
    "build_raw_payload_row",
    "build_result_row",
    "build_worker_history_entry",
    "build_worker_registration",
    "coerce_job_detail",
    "coerce_job_result",
    "coerce_json_object",
    "coerce_json_payload",
    "coerce_record_list",
    "job_is_ready",
    "job_matches_capabilities",
    "job_sort_key",
    "normalize_capabilities",
    "normalize_string_list",
    "normalize_target",
    "normalize_teamwork_config",
    "parse_datetime_value",
    "prepare_table_records",
    "read_teamwork_config",
    "utcnow_iso",
]
