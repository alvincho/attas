"""
Regression tests for Pulser Config Samples.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. These tests cover Attas-specific pulse
definitions, validation flows, and personal-agent integration points.

The pytest cases in this file document expected behavior through checks such as
`test_shipped_pulser_configs_define_sample_parameters`, helping guard against
regressions as the packages evolve.
"""

import json
from pathlib import Path


def test_shipped_pulser_configs_define_sample_parameters():
    """
    Exercise the test_shipped_pulser_configs_define_sample_parameters regression
    scenario.
    """
    root = Path(__file__).resolve().parents[2]
    config_dir = root / "attas" / "configs"
    config_paths = sorted(list(config_dir.glob("*.pulser")) + list(config_dir.glob("*.config")))

    missing: list[str] = []
    for config_path in config_paths:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        supported_pulses = payload.get("supported_pulses") or payload.get("pulser", {}).get("supported_pulses") or []
        for pulse in supported_pulses:
            if not isinstance(pulse, dict):
                continue
            has_inline_sample = isinstance(pulse.get("test_data"), dict) and bool(pulse.get("test_data"))
            has_path_sample = bool(str(pulse.get("test_data_path") or "").strip())
            if has_inline_sample or has_path_sample:
                continue
            pulse_name = str(pulse.get("name") or pulse.get("pulse_name") or "unnamed")
            missing.append(f"{config_path.name}:{pulse_name}")

    assert missing == [], f"Missing sample parameters for supported pulses: {', '.join(missing)}"
