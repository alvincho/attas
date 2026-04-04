"""
Public package exports for `prompits.pools`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the pools package implements
storage adapters and pool-specific helpers.

It re-exports symbols such as `PostgresPool` so callers can import the package through a
stable surface.
"""

from .postgres import PostgresPool

__all__ = ["PostgresPool"]
