import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.pds import PDSValidationError, PulseCatalog, PulseDefinition, PulseMapping, PulseProfile, load_validated_pds_resource


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "pulses"


@pytest.mark.parametrize(
    ("file_name", "expected_type"),
    [
        ("last_trade.json", PulseDefinition),
        ("revenue.json", PulseDefinition),
        ("rsi.json", PulseDefinition),
        ("rating_summary.json", PulseDefinition),
        ("lseg-last-trade.mapping.json", PulseMapping),
        ("attas-equity-research-last-trade.profile.json", PulseProfile),
        ("finance-core.catalog.json", PulseCatalog),
    ],
)
def test_example_pds_resources_validate(file_name, expected_type):
    loaded = load_validated_pds_resource(EXAMPLES_DIR / file_name)

    assert isinstance(loaded.resource, expected_type)
    assert loaded.resource.id
    assert loaded.source_path.name == file_name


def test_invalid_example_pds_resource_reports_readable_error():
    with pytest.raises(PDSValidationError) as exc_info:
        load_validated_pds_resource(EXAMPLES_DIR / "invalid-last-trade.missing-interface.json")

    diagnostics = exc_info.value.diagnostics
    assert diagnostics
    assert any("interface" in diagnostic.message for diagnostic in diagnostics)
    assert diagnostics[0].file_path.endswith("invalid-last-trade.missing-interface.json")
