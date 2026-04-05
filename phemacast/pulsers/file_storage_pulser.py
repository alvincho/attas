"""
Backward-compatible shim for the legacy storage pulser import path.
"""

from phemacast.pulsers.system_storage_pulser import *  # noqa: F401,F403
from phemacast.pulsers.system_storage_pulser import SystemStoragePulser


FileStoragePulser = SystemStoragePulser
