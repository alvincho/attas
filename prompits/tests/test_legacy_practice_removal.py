"""
Regression tests for Legacy Practice Removal.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_removed_legacy_practices_raise_helpful_error`, helping guard against regressions
as the packages evolve.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.create_agent import instantiate_practice_from_config


@pytest.mark.parametrize(
    "practice_type",
    [
        "prompits.practices.chat.ChatPractice",
        "prompits.practices.llm.LLMPractice",
    ],
)
def test_removed_legacy_practices_raise_helpful_error(practice_type):
    """
    Exercise the test_removed_legacy_practices_raise_helpful_error regression
    scenario.
    """
    with pytest.raises(ValueError, match="removed"):
        instantiate_practice_from_config({}, {"type": practice_type})
