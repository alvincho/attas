"""
Regression tests for Map Castr.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_run_map_job_cap_runs_map_castr_with_worker_pool`,
`test_map_castr_executes_map_phema_and_writes_json_artifact`,
`test_map_castr_executes_only_the_selected_branch_path`, and
`test_map_executor_fans_out_to_all_matching_branch_targets_when_route_mode_is_all`,
helping guard against regressions as the packages evolve.
"""

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.castrs.map_castr import MapCastr
from phemacast.jobcaps.map_jobcap import RunMapJobCap
from phemacast.map_phemar.executor import execute_map_phema
from prompits.dispatcher.models import JobDetail
from prompits.pools.filesystem import FileSystemPool


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


def _simple_map_phema():
    """Internal helper for simple map phema."""
    return {
        "phema_id": "daily-ohlc-diagram",
        "name": "Daily OHLC Diagram",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "bars": {"type": "array"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer"},
                "interval": {"type": "string"},
            },
        },
        "meta": {
            "map_phemar": {
                "version": 1,
                "diagram": {
                    "plazaUrl": "http://127.0.0.1:8011",
                    "nodes": [
                        {
                            "id": "mind-boundary-input",
                            "role": "input",
                            "type": "pill",
                            "title": "Input",
                            "outputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                        },
                        {
                            "id": "node-fetch",
                            "type": "rounded",
                            "title": "Fetch OHLC",
                            "pulserName": "ChartPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "ohlc_bar_series",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "interval": {"type": "string"},
                                },
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "bars": {"type": "array"},
                                    "symbol": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "interval": {"type": "string"},
                                },
                            },
                        },
                        {
                            "id": "mind-boundary-output",
                            "role": "output",
                            "type": "pill",
                            "title": "Output",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "bars": {"type": "array"},
                                    "symbol": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "interval": {"type": "string"},
                                },
                            },
                        },
                    ],
                    "edges": [
                        {"id": "edge-input", "from": "mind-boundary-input", "to": "node-fetch", "mappingText": "{}"},
                        {"id": "edge-output", "from": "node-fetch", "to": "mind-boundary-output", "mappingText": "{}"},
                    ],
                },
            }
        },
    }


def _branch_map_phema():
    """Internal helper for branch map phema."""
    return {
        "phema_id": "branch-diagram",
        "name": "Branch Diagram",
        "meta": {
            "map_phemar": {
                "version": 1,
                "diagram": {
                    "plazaUrl": "http://127.0.0.1:8011",
                    "nodes": [
                        {
                            "id": "mind-boundary-input",
                            "role": "input",
                            "type": "pill",
                            "title": "Input",
                            "outputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                        },
                        {
                            "id": "node-branch",
                            "type": "branch",
                            "title": "Route Gate",
                            "conditionExpression": "input_data.get('go', False)",
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                        },
                        {
                            "id": "node-yes",
                            "type": "rounded",
                            "title": "Yes Path",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "yes_path",
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"route": {"type": "string"}}},
                        },
                        {
                            "id": "node-no",
                            "type": "rounded",
                            "title": "No Path",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "no_path",
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"route": {"type": "string"}}},
                        },
                        {
                            "id": "mind-boundary-output",
                            "role": "output",
                            "type": "pill",
                            "title": "Output",
                            "inputSchema": {"type": "object", "properties": {"route": {"type": "string"}}},
                        },
                    ],
                    "edges": [
                        {"id": "edge-input", "from": "mind-boundary-input", "to": "node-branch", "mappingText": "{}"},
                        {"id": "edge-yes", "from": "node-branch", "to": "node-yes", "mappingText": "{}", "route": "yes", "fromAnchor": "branch-yes"},
                        {"id": "edge-no", "from": "node-branch", "to": "node-no", "mappingText": "{}", "route": "no", "fromAnchor": "branch-no"},
                        {"id": "edge-yes-output", "from": "node-yes", "to": "mind-boundary-output", "mappingText": "{}"},
                        {"id": "edge-no-output", "from": "node-no", "to": "mind-boundary-output", "mappingText": "{}"},
                    ],
                },
            }
        },
    }


def _fanout_branch_map_phema(branch_yes_mode="all"):
    """Internal helper for fanout branch map phema."""
    return {
        "phema_id": f"branch-fanout-{branch_yes_mode}",
        "name": "Branch Fanout Diagram",
        "meta": {
            "map_phemar": {
                "version": 1,
                "diagram": {
                    "plazaUrl": "http://127.0.0.1:8011",
                    "nodes": [
                        {
                            "id": "mind-boundary-input",
                            "role": "input",
                            "type": "pill",
                            "title": "Input",
                            "outputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                        },
                        {
                            "id": "node-branch",
                            "type": "branch",
                            "title": "Route Gate",
                            "conditionExpression": "input_data.get('go', False)",
                            "branchYesMode": branch_yes_mode,
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                        },
                        {
                            "id": "node-yes-primary",
                            "type": "rounded",
                            "title": "Yes Primary",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "yes_primary",
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"primary_route": {"type": "string"}}},
                        },
                        {
                            "id": "node-yes-secondary",
                            "type": "rounded",
                            "title": "Yes Secondary",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "yes_secondary",
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"secondary_route": {"type": "string"}}},
                        },
                        {
                            "id": "node-no",
                            "type": "rounded",
                            "title": "No Path",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "no_path",
                            "inputSchema": {"type": "object", "properties": {"go": {"type": "boolean"}}},
                            "outputSchema": {"type": "object", "properties": {"fallback_route": {"type": "string"}}},
                        },
                        {
                            "id": "mind-boundary-output",
                            "role": "output",
                            "type": "pill",
                            "title": "Output",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "primary_route": {"type": "string"},
                                    "secondary_route": {"type": "string"},
                                    "fallback_route": {"type": "string"},
                                },
                            },
                        },
                    ],
                    "edges": [
                        {"id": "edge-input", "from": "mind-boundary-input", "to": "node-branch", "mappingText": "{}"},
                        {"id": "edge-yes-primary", "from": "node-branch", "to": "node-yes-primary", "mappingText": "{}", "route": "yes", "fromAnchor": "branch-yes"},
                        {"id": "edge-yes-secondary", "from": "node-branch", "to": "node-yes-secondary", "mappingText": "{}", "route": "yes", "fromAnchor": "branch-yes"},
                        {"id": "edge-no", "from": "node-branch", "to": "node-no", "mappingText": "{}", "route": "no", "fromAnchor": "branch-no"},
                        {"id": "edge-yes-primary-output", "from": "node-yes-primary", "to": "mind-boundary-output", "mappingText": "{}"},
                        {"id": "edge-yes-secondary-output", "from": "node-yes-secondary", "to": "mind-boundary-output", "mappingText": "{}"},
                        {"id": "edge-no-output", "from": "node-no", "to": "mind-boundary-output", "mappingText": "{}"},
                    ],
                },
            }
        },
    }


def _multi_input_branch_map_phema(branch_input_mode="any"):
    """Internal helper for multi input branch map phema."""
    return {
        "phema_id": f"branch-multi-input-{branch_input_mode}",
        "name": "Branch Multi Input Diagram",
        "meta": {
            "map_phemar": {
                "version": 1,
                "diagram": {
                    "plazaUrl": "http://127.0.0.1:8011",
                    "nodes": [
                        {
                            "id": "mind-boundary-input",
                            "role": "input",
                            "type": "pill",
                            "title": "Input",
                            "outputSchema": {"type": "object", "properties": {"seed": {"type": "boolean"}}},
                        },
                        {
                            "id": "node-seed",
                            "type": "rounded",
                            "title": "Seed",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "seed_path",
                            "inputSchema": {"type": "object", "properties": {"seed": {"type": "boolean"}}},
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "id": "node-left-branch",
                            "type": "branch",
                            "title": "Left Branch",
                            "conditionExpression": "input_data.get('go_left', False)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "id": "node-right-branch",
                            "type": "branch",
                            "title": "Right Branch",
                            "conditionExpression": "input_data.get('go_right', False)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "id": "node-join-branch",
                            "type": "branch",
                            "title": "Join Branch",
                            "conditionExpression": "input_data.get('go_left', False)",
                            "branchInputMode": branch_input_mode,
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "id": "node-left-no",
                            "type": "rounded",
                            "title": "Left No Sink",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "left_no_sink",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {"type": "object", "properties": {"left_no": {"type": "string"}}},
                        },
                        {
                            "id": "node-right-no",
                            "type": "rounded",
                            "title": "Right No Sink",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "right_no_sink",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {"type": "object", "properties": {"right_no": {"type": "string"}}},
                        },
                        {
                            "id": "node-join-yes",
                            "type": "rounded",
                            "title": "Join Yes Sink",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "target_yes_sink",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {"type": "object", "properties": {"target": {"type": "string"}}},
                        },
                        {
                            "id": "node-join-no",
                            "type": "rounded",
                            "title": "Join No Sink",
                            "pulserName": "DecisionPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "target_no_sink",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "go_left": {"type": "boolean"},
                                    "go_right": {"type": "boolean"},
                                },
                            },
                            "outputSchema": {"type": "object", "properties": {"target": {"type": "string"}}},
                        },
                        {
                            "id": "mind-boundary-output",
                            "role": "output",
                            "type": "pill",
                            "title": "Output",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "left_no": {"type": "string"},
                                    "right_no": {"type": "string"},
                                    "target": {"type": "string"},
                                },
                            },
                        },
                    ],
                    "edges": [
                        {"id": "edge-input", "from": "mind-boundary-input", "to": "node-seed", "mappingText": "{}"},
                        {"id": "edge-seed-left", "from": "node-seed", "to": "node-left-branch", "mappingText": "{}"},
                        {"id": "edge-seed-right", "from": "node-seed", "to": "node-right-branch", "mappingText": "{}"},
                        {"id": "edge-left-yes", "from": "node-left-branch", "to": "node-join-branch", "mappingText": "{}", "route": "yes", "fromAnchor": "branch-yes"},
                        {"id": "edge-left-no", "from": "node-left-branch", "to": "node-left-no", "mappingText": "{}", "route": "no", "fromAnchor": "branch-no"},
                        {"id": "edge-right-yes", "from": "node-right-branch", "to": "node-join-branch", "mappingText": "{}", "route": "yes", "fromAnchor": "branch-yes"},
                        {"id": "edge-right-no", "from": "node-right-branch", "to": "node-right-no", "mappingText": "{}", "route": "no", "fromAnchor": "branch-no"},
                        {"id": "edge-join-yes", "from": "node-join-branch", "to": "node-join-yes", "mappingText": "{}", "route": "yes", "fromAnchor": "branch-yes"},
                        {"id": "edge-join-no", "from": "node-join-branch", "to": "node-join-no", "mappingText": "{}", "route": "no", "fromAnchor": "branch-no"},
                        {"id": "edge-left-no-output", "from": "node-left-no", "to": "mind-boundary-output", "mappingText": "{}"},
                        {"id": "edge-right-no-output", "from": "node-right-no", "to": "mind-boundary-output", "mappingText": "{}"},
                        {"id": "edge-join-yes-output", "from": "node-join-yes", "to": "mind-boundary-output", "mappingText": "{}"},
                        {"id": "edge-join-no-output", "from": "node-join-no", "to": "mind-boundary-output", "mappingText": "{}"},
                    ],
                },
            }
        },
    }


def test_map_castr_executes_map_phema_and_writes_json_artifact(tmp_path):
    """
    Exercise the test_map_castr_executes_map_phema_and_writes_json_artifact
    regression scenario.
    """
    calls = []

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        calls.append({"url": url, "json": json, "timeout": timeout})
        assert url == "http://127.0.0.1:8011/api/pulsers/test"
        return FakeResponse(
            {
                "status": "success",
                "result": {
                    "symbol": json["input"]["symbol"],
                    "limit": json["input"]["limit"],
                    "interval": json["input"]["interval"],
                    "bars": [1, 2, 3],
                },
            }
        )

    pool = FileSystemPool("map_pool", "Temporary storage for map castr tests", str(tmp_path))
    castr = MapCastr(name="MapCastr", pool=pool, auto_register=False, request_post=fake_post)

    result = castr.cast(
        _simple_map_phema(),
        format="json",
        preferences={
            "input": {"symbol": "AAPL"},
            "extra_parameters": {"limit": 5},
            "node_parameters": {"node-fetch": {"interval": "1d"}},
        },
    )

    assert result["status"] == "success"
    assert result["format"] == "JSON"
    assert result["result"]["bars"] == [1, 2, 3]
    assert result["result"]["limit"] == 5
    assert result["result"]["interval"] == "1d"
    assert len(calls) == 1
    assert calls[0]["json"]["input"] == {"symbol": "AAPL", "limit": 5, "interval": "1d"}

    output_path = tmp_path / result["location"]
    assert output_path.exists()
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["execution"]["output"]["bars"] == [1, 2, 3]
    assert artifact["execution"]["step_count"] == 3


def test_map_castr_executes_only_the_selected_branch_path(tmp_path):
    """
    Exercise the test_map_castr_executes_only_the_selected_branch_path regression
    scenario.
    """
    calls = []

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        calls.append(json["pulse_name"])
        route = "yes" if json["pulse_name"] == "yes_path" else "no"
        return FakeResponse({"status": "success", "result": {"route": route}})

    pool = FileSystemPool("branch_map_pool", "Temporary storage for branching map castr tests", str(tmp_path))
    castr = MapCastr(name="BranchMapCastr", pool=pool, auto_register=False, request_post=fake_post)

    result = castr.cast(
        _branch_map_phema(),
        format="json",
        preferences={"input": {"go": True}},
    )

    assert result["status"] == "success"
    assert result["result"]["route"] == "yes"
    assert calls == ["yes_path"]
    branch_step = next(step for step in result["steps"] if step["kind"] == "branch")
    assert branch_step["selected_route"] == "yes"


def test_map_executor_fans_out_to_all_matching_branch_targets_when_route_mode_is_all():
    """
    Exercise the
    test_map_executor_fans_out_to_all_matching_branch_targets_when_route_mode_is_all
    regression scenario.
    """
    calls = []

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        calls.append(json["pulse_name"])
        if json["pulse_name"] == "yes_primary":
            return FakeResponse({"status": "success", "result": {"primary_route": "primary"}})
        if json["pulse_name"] == "yes_secondary":
            return FakeResponse({"status": "success", "result": {"secondary_route": "secondary"}})
        return FakeResponse({"status": "success", "result": {"fallback_route": "fallback"}})

    result = execute_map_phema(
        _fanout_branch_map_phema("all"),
        input_data={"go": True},
        request_post=fake_post,
    )

    assert result["status"] == "success"
    assert result["output"]["primary_route"] == "primary"
    assert result["output"]["secondary_route"] == "secondary"
    assert "fallback_route" not in result["output"]
    assert calls == ["yes_primary", "yes_secondary"]


def test_map_executor_uses_only_the_first_matching_branch_target_when_route_mode_is_any():
    """
    Exercise the test_map_executor_uses_only_the_first_matching_branch_target_when_r
    oute_mode_is_any regression scenario.
    """
    calls = []

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        calls.append(json["pulse_name"])
        if json["pulse_name"] == "yes_primary":
            return FakeResponse({"status": "success", "result": {"primary_route": "primary"}})
        if json["pulse_name"] == "yes_secondary":
            return FakeResponse({"status": "success", "result": {"secondary_route": "secondary"}})
        return FakeResponse({"status": "success", "result": {"fallback_route": "fallback"}})

    result = execute_map_phema(
        _fanout_branch_map_phema("any"),
        input_data={"go": True},
        request_post=fake_post,
    )

    assert result["status"] == "success"
    assert result["output"]["primary_route"] == "primary"
    assert "secondary_route" not in result["output"]
    assert "fallback_route" not in result["output"]
    assert calls == ["yes_primary"]


def test_map_executor_respects_branch_input_any_vs_all():
    """
    Exercise the test_map_executor_respects_branch_input_any_vs_all regression
    scenario.
    """
    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        pulse_name = json["pulse_name"]
        if pulse_name == "seed_path":
            return FakeResponse({"status": "success", "result": {"go_left": True, "go_right": False}})
        if pulse_name == "left_no_sink":
            return FakeResponse({"status": "success", "result": {"left_no": "left-no"}})
        if pulse_name == "right_no_sink":
            return FakeResponse({"status": "success", "result": {"right_no": "right-no"}})
        if pulse_name == "target_yes_sink":
            return FakeResponse({"status": "success", "result": {"target": "joined"}})
        return FakeResponse({"status": "success", "result": {"target": "missed"}})

    any_result = execute_map_phema(
        _multi_input_branch_map_phema("any"),
        input_data={"seed": True},
        request_post=fake_post,
    )
    any_join_step = next(step for step in any_result["steps"] if step["node_id"] == "node-join-branch")
    assert any_join_step["status"] == "ready"
    assert any_result["output"]["target"] == "joined"
    assert any_result["output"]["right_no"] == "right-no"

    all_result = execute_map_phema(
        _multi_input_branch_map_phema("all"),
        input_data={"seed": True},
        request_post=fake_post,
    )
    all_join_step = next(step for step in all_result["steps"] if step["node_id"] == "node-join-branch")
    assert all_join_step["status"] == "skipped"
    assert all_join_step["error"] == "Waiting for all inbound branch connections before evaluating this branch."
    assert "target" not in all_result["output"]
    assert all_result["output"]["right_no"] == "right-no"


def test_run_map_job_cap_runs_map_castr_with_worker_pool(tmp_path):
    """
    Exercise the test_run_map_job_cap_runs_map_castr_with_worker_pool regression
    scenario.
    """
    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        return FakeResponse(
            {
                "status": "success",
                "result": {
                    "symbol": json["input"]["symbol"],
                    "limit": json["input"]["limit"],
                    "interval": json["input"]["interval"],
                    "bars": [8, 13, 21],
                },
            }
        )

    pool = FileSystemPool("jobcap_map_pool", "Temporary storage for map jobcap tests", str(tmp_path))
    worker = SimpleNamespace(pool=pool, worker_id="dispatcher-worker:map-1", name="MapWorker")
    cap = RunMapJobCap(request_post=fake_post).bind_worker(worker)
    job = JobDetail.model_validate(
        {
            "id": "dispatcher-job:run-map:test",
            "required_capability": "run map",
            "payload": {
                "phema": _simple_map_phema(),
                "input": {"symbol": "TSLA"},
                "extra_parameters": {"limit": 7},
                "node_parameters": {"node-fetch": {"interval": "4h"}},
            },
        }
    )

    result = cap.finish(job)

    assert result.status == "completed"
    assert result.target_table == "dispatcher_map_runs"
    assert result.result_summary["rows"] == 1
    assert result.result_summary["steps"] == 3
    assert result.collected_rows[0]["phema_id"] == "daily-ohlc-diagram"
    assert result.collected_rows[0]["result"]["bars"] == [8, 13, 21]
    assert result.raw_payload["result"]["interval"] == "4h"
