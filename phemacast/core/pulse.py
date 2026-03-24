# Pulse is a Pit can be registered on a Plaza
# The Pulse on a Plaza is like data dictionary, provide standard data format and definition for all agents connected to the Plaza
# Pulse is searchable on Plaza
# Pluse contains the following properties in addition to those inherited from Pit
# * output_schema: a JSON schema

from .pit import Pit

class Pulse(Pit):
    def __init__(self, plaza, name, output_schema: dict):
        super().__init__(plaza, name)
        self.output_schema = output_schema