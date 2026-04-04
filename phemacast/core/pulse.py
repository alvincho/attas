"""
Pulse module for `phemacast.core.pulse`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the core package defines the domain models
that describe pulses, phemas, and participating parties.

Core types exposed here include `Pulse`, which carry the main behavior or state managed
by this module.
"""

# Pulse is a Pit can be registered on a Plaza
# The Pulse on a Plaza is like data dictionary, provide standard data format and definition for all agents connected to the Plaza
# Pulse is searchable on Plaza
# Pluse contains the following properties in addition to those inherited from Pit
# * output_schema: a JSON schema

from .pit import Pit

class Pulse(Pit):
    """Represent a pulse."""
    def __init__(self, plaza, name, output_schema: dict):
        """Initialize the pulse."""
        super().__init__(plaza, name)
        self.output_schema = output_schema