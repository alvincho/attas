"""
Regression tests for PDS Catalog.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. These tests cover Attas-specific pulse
definitions, validation flows, and personal-agent integration points.

The pytest cases in this file document expected behavior through checks such as
`test_build_pds_resource_index_tracks_invalid_resources`,
`test_catalog_bundle_reports_unresolved_item_refs`,
`test_finance_core_catalog_bundle_resolves_example_resources`, and
`test_catalog_bundle_deduplicates_duplicate_refs`, helping guard against regressions as
the packages evolve.
"""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.pds import build_pds_resource_index, load_catalog_bundle, resolve_catalog_by_id


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "pulses"


def test_finance_core_catalog_bundle_resolves_example_resources():
    """
    Exercise the test_finance_core_catalog_bundle_resolves_example_resources
    regression scenario.
    """
    bundle = load_catalog_bundle(EXAMPLES_DIR / "finance-core.catalog.json")

    assert bundle.catalog.resource.id == "ai.attas.catalog.finance_core"
    assert set(bundle.definitions) == {
        "ai.attas.finance.price.last_trade",
        "ai.attas.finance.fundamentals.revenue",
        "ai.attas.finance.technical.rsi",
        "ai.attas.finance.research.rating_summary",
    }
    assert set(bundle.mappings) == {"ai.attas.mapping.lseg.last_trade"}
    assert set(bundle.profiles) == {"ai.attas.profile.equity_research.last_trade"}
    assert bundle.unresolved_refs == []
    assert bundle.unresolved_imports == ["ai.attas.catalog.common"]
    assert any(diagnostic.code == "unresolved_catalog_import" for diagnostic in bundle.diagnostics)


def test_build_pds_resource_index_tracks_invalid_resources():
    """
    Exercise the test_build_pds_resource_index_tracks_invalid_resources regression
    scenario.
    """
    index = build_pds_resource_index([EXAMPLES_DIR])

    assert "ai.attas.finance.price.last_trade" in index.resources_by_id
    assert "ai.attas.catalog.finance_core" in index.resources_by_id
    assert "ai.attas.finance.price.last_trade.invalid_missing_interface" in index.invalid_by_id


def test_catalog_bundle_reports_unresolved_item_refs(tmp_path):
    """
    Exercise the test_catalog_bundle_reports_unresolved_item_refs regression
    scenario.
    """
    shutil.copy(EXAMPLES_DIR / "last_trade.json", tmp_path / "last_trade.json")
    (tmp_path / "catalog.json").write_text(
        json.dumps(
            {
                "pds_version": "0.1.0",
                "resource_type": "pulse_catalog",
                "id": "ai.attas.catalog.synthetic",
                "version": "1.0.0",
                "items": [
                    {"ref": "ai.attas.finance.price.last_trade"},
                    {"ref": "ai.attas.finance.price.missing_trade"},
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle = load_catalog_bundle(tmp_path / "catalog.json", search_directories=[tmp_path])

    assert set(bundle.definitions) == {"ai.attas.finance.price.last_trade"}
    assert bundle.unresolved_refs == ["ai.attas.finance.price.missing_trade"]
    assert any(diagnostic.code == "unresolved_catalog_ref" for diagnostic in bundle.diagnostics)


def test_catalog_bundle_reports_invalid_referenced_resources(tmp_path):
    """
    Exercise the test_catalog_bundle_reports_invalid_referenced_resources regression
    scenario.
    """
    (tmp_path / "invalid-last-trade.json").write_text(
        json.dumps(
            {
                "pds_version": "0.1.0",
                "resource_type": "pulse_definition",
                "id": "ai.attas.finance.price.last_trade",
                "namespace": "ai.attas.finance.price",
                "name": "last_trade",
                "version": "1.0.0",
                "title": "Invalid Last Trade Price Example",
                "description": "Negative test case: missing interface object.",
                "pulse_class": "fact",
                "status": "stable",
                "concept": {
                    "definition": "Most recent executed trade price for a financial instrument on a specified venue or consolidated feed."
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "catalog.json").write_text(
        json.dumps(
            {
                "pds_version": "0.1.0",
                "resource_type": "pulse_catalog",
                "id": "ai.attas.catalog.synthetic_invalid",
                "version": "1.0.0",
                "items": [
                    {"ref": "ai.attas.finance.price.last_trade"},
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle = load_catalog_bundle(tmp_path / "catalog.json", search_directories=[tmp_path])

    assert bundle.definitions == {}
    assert bundle.invalid_refs == ["ai.attas.finance.price.last_trade"]
    assert any(diagnostic.code == "invalid_catalog_ref" for diagnostic in bundle.diagnostics)


def test_catalog_bundle_deduplicates_duplicate_refs(tmp_path):
    """
    Exercise the test_catalog_bundle_deduplicates_duplicate_refs regression
    scenario.
    """
    shutil.copy(EXAMPLES_DIR / "last_trade.json", tmp_path / "last_trade.json")
    (tmp_path / "catalog.json").write_text(
        json.dumps(
            {
                "pds_version": "0.1.0",
                "resource_type": "pulse_catalog",
                "id": "ai.attas.catalog.synthetic_deduped",
                "version": "1.0.0",
                "items": [
                    {"ref": "ai.attas.finance.price.last_trade"},
                    {"ref": "ai.attas.finance.price.last_trade"},
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle = resolve_catalog_by_id("ai.attas.catalog.synthetic_deduped", tmp_path)

    assert set(bundle.definitions) == {"ai.attas.finance.price.last_trade"}
    assert bundle.unresolved_refs == []
