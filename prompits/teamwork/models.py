"""
Typed data models for `prompits.teamwork.models`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

The file is intentionally lightweight, but its placement in the package makes it part of
the documented module surface.
"""

from prompits.dispatcher.models import JOB_TIMESTAMP_FIELDS, JobDetail, JobResult

__all__ = ["JOB_TIMESTAMP_FIELDS", "JobDetail", "JobResult"]
