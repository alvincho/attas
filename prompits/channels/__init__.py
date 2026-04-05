"""
Public package exports for `prompits.channels`.

Prompits is the base framework layer for FinMAS. The channels package exposes the
small, generic delivery-lane helpers that higher layers can use for Slack, Teams,
email, and destination publishing status.
"""

from prompits.channels.runtime import (
    B2B_CHANNEL_KINDS,
    build_delivery_snapshot,
    default_b2b_channels,
    normalize_channel_lane,
)


__all__ = [
    "B2B_CHANNEL_KINDS",
    "build_delivery_snapshot",
    "default_b2b_channels",
    "normalize_channel_lane",
]
