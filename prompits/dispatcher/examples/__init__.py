"""
Public package exports for `prompits.dispatcher.examples`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

It re-exports symbols such as `echo_job_cap` so callers can import the package through a
stable surface.
"""

from prompits.dispatcher.examples.job_caps import echo_job_cap

__all__ = ["echo_job_cap"]
