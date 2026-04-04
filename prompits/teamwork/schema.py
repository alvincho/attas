"""
Schema definitions for `prompits.teamwork.schema`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

The file is intentionally lightweight, but its placement in the package makes it part of
the documented module surface.
"""

from prompits.dispatcher.schema import (
    CAPABILITY_TO_TABLE,
    TABLE_JOBS,
    TABLE_RAW_PAYLOADS,
    TABLE_RESULT_ROWS,
    TABLE_WORKER_HISTORY,
    TABLE_WORKERS,
    dispatcher_table_schema_map,
    ensure_dispatcher_tables,
    jobs_schema_dict,
)

__all__ = [
    "CAPABILITY_TO_TABLE",
    "TABLE_JOBS",
    "TABLE_RAW_PAYLOADS",
    "TABLE_RESULT_ROWS",
    "TABLE_WORKER_HISTORY",
    "TABLE_WORKERS",
    "dispatcher_table_schema_map",
    "ensure_dispatcher_tables",
    "jobs_schema_dict",
]
