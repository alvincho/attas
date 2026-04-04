"""
Pulse Builder module for `prompits.agents.pulse_builder`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, these modules provide reusable
agent hosts and user-facing agent variants.

The file is intentionally lightweight, but its placement in the package makes it part of
the documented module surface.
"""

# PulseBuilder is an standby agent to add new Pulses and Pulsers into plaza
# BuildPulse is a practice that can be used to create new Pulses and Pulsers
# - a prompt as parameter to indicate what pulse or pulser to build
# - 