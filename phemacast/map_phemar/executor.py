"""
Execution helpers for `phemacast.map_phemar.executor`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the map_phemar package supports map-oriented
phema execution and its UI/runtime helpers.

Key definitions include `MapExecutionError` and `execute_map_phema`, which provide the
main entry points used by neighboring modules and tests.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Sequence

import requests

from phemacast.map_phemar.runtime import evaluate_branch_condition
from phemacast.personal_agent.plaza import normalize_plaza_url


RequestPost = Callable[..., Any]


class MapExecutionError(RuntimeError):
    """Raised when a diagram-backed Phema cannot be executed."""


def _utcnow_iso() -> str:
    """Internal helper for utcnow iso."""
    return datetime.now(timezone.utc).isoformat()


def _clone(value: Any) -> Any:
    """Internal helper for clone."""
    return copy.deepcopy(value)


def _is_mapping(value: Any) -> bool:
    """Return whether the value is a mapping."""
    return isinstance(value, Mapping)


def _coerce_mapping(value: Any, *, label: str) -> Dict[str, Any]:
    """Internal helper to coerce the mapping."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    raise MapExecutionError(f"{label} must be a JSON object.")


def _parse_json_object(value: Any, *, label: str) -> Dict[str, Any]:
    """Internal helper to parse the JSON object."""
    if value is None or value == "":
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str):
        raise MapExecutionError(f"{label} must be a JSON object.")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise MapExecutionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise MapExecutionError(f"{label} must be a JSON object.")
    return parsed


def _normalize_boundary_role(role: Any) -> str:
    """Internal helper to normalize the boundary role."""
    normalized = str(role or "").strip().lower()
    if normalized in {"start", "input"}:
        return "input"
    if normalized in {"end", "output"}:
        return "output"
    return ""


def _normalize_branch_route(value: Any) -> str:
    """Internal helper to normalize the branch route."""
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "branch-yes"}:
        return "yes"
    if normalized in {"no", "branch-no"}:
        return "no"
    return ""


def _normalize_branch_connector_mode(value: Any, *, fallback: str = "all") -> str:
    """Internal helper to normalize the branch connector mode."""
    normalized = str(value or "").strip().lower()
    if normalized in {"any", "all"}:
        return normalized
    return fallback


def _default_branch_connector_mode(kind: str) -> str:
    """Internal helper to return the default branch connector mode."""
    return "any" if str(kind or "").strip().lower() == "input" else "all"


def _branch_connector_mode(node: Mapping[str, Any], kind: str) -> str:
    """Internal helper for branch connector mode."""
    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind == "input":
        return _normalize_branch_connector_mode(
            node.get("branchInputMode"),
            fallback=_default_branch_connector_mode("input"),
        )
    if normalized_kind == "yes":
        return _normalize_branch_connector_mode(
            node.get("branchYesMode"),
            fallback=_default_branch_connector_mode("yes"),
        )
    return _normalize_branch_connector_mode(
        node.get("branchNoMode"),
        fallback=_default_branch_connector_mode("no"),
    )


def _is_boundary_node(node: Mapping[str, Any] | None) -> bool:
    """Return whether the value is a boundary node."""
    return bool(_normalize_boundary_role((node or {}).get("role")))


def _is_branch_node(node: Mapping[str, Any] | None) -> bool:
    """Return whether the value is a branch node."""
    return not _is_boundary_node(node) and str((node or {}).get("type") or "").strip().lower() == "branch"


def _schema_properties(schema: Any) -> Dict[str, Any]:
    """Internal helper to return the schema properties."""
    if isinstance(schema, Mapping) and isinstance(schema.get("properties"), Mapping):
        return dict(schema.get("properties") or {})
    if isinstance(schema, Mapping):
        return dict(schema)
    return {}


def _schema_required(schema: Any) -> List[str]:
    """Internal helper to return the schema required."""
    if isinstance(schema, Mapping) and isinstance(schema.get("required"), list) and schema.get("required"):
        return [str(entry) for entry in schema.get("required") if str(entry).strip()]
    return list(_schema_properties(schema).keys())


def _schema_field_names(schema: Any) -> List[str]:
    """Internal helper to return the schema field names."""
    required = _schema_required(schema)
    if required:
        return required
    return list(_schema_properties(schema).keys())


def _read_path(value: Any, path: str) -> Any:
    """Internal helper to read the path."""
    if not path:
        return value
    current = value
    for token in str(path).replace("[", ".").replace("]", "").split("."):
        if not token:
            continue
        if current is None:
            return None
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            if not token.isdigit():
                return None
            index = int(token)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        if not isinstance(current, Mapping):
            return None
        current = current.get(token)
    return current


def _write_path_value(target: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """Internal helper to write the path value."""
    if not path:
        if isinstance(value, Mapping):
            return dict(value)
        return {"value": _clone(value)}
    tokens = [token for token in str(path).replace("[", ".").replace("]", "").split(".") if token]
    if not tokens:
        if isinstance(value, Mapping):
            return dict(value)
        return {"value": _clone(value)}
    current: Any = target
    for index, token in enumerate(tokens):
        key: Any = int(token) if token.isdigit() else token
        is_last = index == len(tokens) - 1
        next_token = tokens[index + 1] if not is_last else ""
        next_is_array = next_token.isdigit()
        if is_last:
            current[key] = _clone(value)
            break
        next_value = current.get(key) if isinstance(current, Mapping) else None
        if not isinstance(next_value, (dict, list)):
            current[key] = [] if next_is_array else {}
        current = current[key]
    return target


def _merge_structured_data(target: Any, source: Any) -> Any:
    """Internal helper to merge the structured data."""
    if not isinstance(source, Mapping):
        return _clone(source)
    base = dict(target) if isinstance(target, Mapping) else {}
    for key, value in source.items():
        if isinstance(value, Mapping):
            base[key] = _merge_structured_data(base.get(key), value)
        else:
            base[key] = _clone(value)
    return base


def _parse_edge_mapping(edge: Mapping[str, Any]) -> Dict[str, Any]:
    """Internal helper to parse the edge mapping."""
    mapping_text = str(edge.get("mappingText") or "{}")
    try:
        parsed = json.loads(mapping_text)
    except json.JSONDecodeError as exc:
        edge_id = str(edge.get("id") or "unknown-edge")
        raise MapExecutionError(f"Edge '{edge_id}' contains invalid mapping JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        edge_id = str(edge.get("id") or "unknown-edge")
        raise MapExecutionError(f"Edge '{edge_id}' mapping must be a JSON object.")
    return parsed


def _mapped_source_field(mapping_value: Any, fallback_field: str) -> str:
    """Internal helper for mapped source field."""
    if isinstance(mapping_value, str):
        return mapping_value.strip()
    if isinstance(mapping_value, Mapping) and isinstance(mapping_value.get("from"), str):
        return str(mapping_value.get("from") or "").strip()
    return fallback_field


def _has_mapped_constant(mapping_value: Any) -> bool:
    """Return whether the value has mapped constant."""
    return isinstance(mapping_value, Mapping) and "const" in mapping_value


def _mapped_constant_runtime_value(mapping_value: Any) -> Any:
    """Internal helper to return the mapped constant runtime value."""
    if not _has_mapped_constant(mapping_value):
        return None
    raw = mapping_value.get("const")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return _clone(raw)


def _build_mapped_edge_payload(source_output: Any, target_node: Mapping[str, Any], edge: Mapping[str, Any]) -> Dict[str, Any]:
    """Internal helper to build the mapped edge payload."""
    mapping = _parse_edge_mapping(edge)
    payload: Dict[str, Any] = {}
    target_paths = list(dict.fromkeys(_schema_field_names(target_node.get("inputSchema") or {}) + list(mapping.keys())))
    if not target_paths and not mapping:
        if isinstance(source_output, Mapping):
            return dict(source_output)
        return {"value": _clone(source_output)}
    for target_path in target_paths:
        mapping_value = mapping.get(target_path)
        if _has_mapped_constant(mapping_value):
            _write_path_value(payload, target_path, _mapped_constant_runtime_value(mapping_value))
            continue
        fallback_field = target_path if target_path in _schema_field_names(target_node.get("inputSchema") or {}) else ""
        source_field = _mapped_source_field(mapping_value, fallback_field)
        if not source_field:
            continue
        next_value = _read_path(source_output, source_field)
        if next_value is None:
            continue
        _write_path_value(payload, target_path, next_value)
    return payload


def _outgoing_edges(diagram: Mapping[str, Any], node_id: str) -> List[Dict[str, Any]]:
    """Internal helper for outgoing edges."""
    return [dict(edge) for edge in (diagram.get("edges") or []) if str(edge.get("from") or "") == node_id]


def _incoming_edges(diagram: Mapping[str, Any], node_id: str) -> List[Dict[str, Any]]:
    """Internal helper for incoming edges."""
    return [dict(edge) for edge in (diagram.get("edges") or []) if str(edge.get("to") or "") == node_id]


def _branch_connection_counts(
    diagram: Mapping[str, Any],
    node_id: str,
    *,
    relevant_ids: set[str] | None = None,
) -> Dict[str, int]:
    """Internal helper for branch connection counts."""
    def _includes(target_id: str) -> bool:
        """Internal helper for includes."""
        return relevant_ids is None or target_id in relevant_ids

    incoming = [
        edge
        for edge in _incoming_edges(diagram, node_id)
        if _includes(str(edge.get("from") or ""))
    ]
    outgoing = [
        edge
        for edge in _outgoing_edges(diagram, node_id)
        if _includes(str(edge.get("to") or ""))
    ]
    return {
        "input": len(incoming),
        "yes": len([edge for edge in outgoing if _normalize_branch_route(edge.get("route") or edge.get("fromAnchor")) == "yes"]),
        "no": len([edge for edge in outgoing if _normalize_branch_route(edge.get("route") or edge.get("fromAnchor")) == "no"]),
    }


def _branch_input_ready(
    node: Mapping[str, Any],
    *,
    active_incoming_edges: Sequence[Mapping[str, Any]],
    connected_incoming_edges: Sequence[Mapping[str, Any]],
) -> bool:
    """Internal helper for branch input ready."""
    if not connected_incoming_edges:
        return False
    if _branch_connector_mode(node, "input") == "all":
        return len(active_incoming_edges) == len(connected_incoming_edges)
    return bool(active_incoming_edges)


def _active_branch_route_edges(
    node: Mapping[str, Any],
    outgoing_edges: Sequence[Mapping[str, Any]],
    route: str,
) -> List[Dict[str, Any]]:
    """Internal helper to return the active branch route edges."""
    matching = [
        dict(edge)
        for edge in outgoing_edges
        if _normalize_branch_route(edge.get("route") or edge.get("fromAnchor")) == route
    ]
    if _branch_connector_mode(node, route) == "any":
        return matching[:1]
    return matching


def _edge_has_active_payload(
    edge: Mapping[str, Any],
    nodes_by_id: Mapping[str, Mapping[str, Any]],
    step_outputs: Mapping[str, Any],
    active_branch_edge_ids: set[str],
) -> bool:
    """Return whether the edge has active payload."""
    source_id = str(edge.get("from") or "")
    if source_id not in step_outputs:
        return False
    source_node = nodes_by_id.get(source_id)
    if source_node and _is_branch_node(source_node):
        return str(edge.get("id") or "") in active_branch_edge_ids
    return True


def _collect_reachable(diagram: Mapping[str, Any], start_id: str, direction: str = "out") -> set[str]:
    """Internal helper to collect the reachable."""
    visited: set[str] = set()
    queue = [str(start_id or "")]
    while queue:
        current_id = queue.pop(0)
        if not current_id or current_id in visited:
            continue
        visited.add(current_id)
        edges = _incoming_edges(diagram, current_id) if direction == "in" else _outgoing_edges(diagram, current_id)
        for edge in edges:
            queue.append(str(edge.get("from") if direction == "in" else edge.get("to") or ""))
    return visited


def _diagram_from_phema(phema: Mapping[str, Any]) -> Dict[str, Any]:
    """Internal helper for diagram from phema."""
    meta = dict(phema.get("meta") or {}) if isinstance(phema.get("meta"), Mapping) else {}
    map_meta = dict(meta.get("map_phemar") or {}) if isinstance(meta.get("map_phemar"), Mapping) else {}
    diagram = dict(map_meta.get("diagram") or {}) if isinstance(map_meta.get("diagram"), Mapping) else {}
    if not diagram:
        raise MapExecutionError("Phema does not contain a MapPhemar diagram.")
    nodes = [dict(node) for node in (diagram.get("nodes") or []) if isinstance(node, Mapping)]
    edges = [dict(edge) for edge in (diagram.get("edges") or []) if isinstance(edge, Mapping)]
    if not nodes:
        raise MapExecutionError("MapPhemar diagram does not contain any nodes.")
    return {
        **diagram,
        "nodes": nodes,
        "edges": edges,
    }


def _boundary_node(diagram: Mapping[str, Any], role: str) -> Dict[str, Any] | None:
    """Internal helper for boundary node."""
    normalized = _normalize_boundary_role(role)
    for node in diagram.get("nodes") or []:
        if _normalize_boundary_role(node.get("role")) == normalized:
            return dict(node)
    return None


def _topological_order(
    diagram: Mapping[str, Any],
    *,
    relevant_ids: set[str],
) -> List[Dict[str, Any]]:
    """Internal helper for topological order."""
    runnable_nodes = [
        dict(node)
        for node in (diagram.get("nodes") or [])
        if str(node.get("id") or "") in relevant_ids and not _is_boundary_node(node)
    ]
    order_index = {str(node.get("id") or ""): index for index, node in enumerate(diagram.get("nodes") or [])}
    runnable_ids = {str(node.get("id") or "") for node in runnable_nodes}
    indegree = {node_id: 0 for node_id in runnable_ids}
    relevant_edges = [
        dict(edge)
        for edge in (diagram.get("edges") or [])
        if str(edge.get("from") or "") in relevant_ids and str(edge.get("to") or "") in relevant_ids
    ]
    for edge in relevant_edges:
        source_id = str(edge.get("from") or "")
        target_id = str(edge.get("to") or "")
        if source_id in runnable_ids and target_id in runnable_ids:
            indegree[target_id] = indegree.get(target_id, 0) + 1

    queue = sorted(
        [node for node in runnable_nodes if indegree.get(str(node.get("id") or ""), 0) == 0],
        key=lambda node: order_index.get(str(node.get("id") or ""), 0),
    )
    ordered: List[Dict[str, Any]] = []
    while queue:
        node = queue.pop(0)
        node_id = str(node.get("id") or "")
        ordered.append(node)
        for edge in relevant_edges:
            if str(edge.get("from") or "") != node_id:
                continue
            target_id = str(edge.get("to") or "")
            if target_id not in runnable_ids:
                continue
            indegree[target_id] = indegree.get(target_id, 0) - 1
            if indegree[target_id] == 0:
                next_node = next((entry for entry in runnable_nodes if str(entry.get("id") or "") == target_id), None)
                if next_node and all(str(entry.get("id") or "") != target_id for entry in ordered + queue):
                    queue.append(next_node)
                    queue.sort(key=lambda entry: order_index.get(str(entry.get("id") or ""), 0))
    if len(ordered) != len(runnable_nodes):
        raise MapExecutionError("Diagram execution requires a directed acyclic flow.")
    return ordered


def _resolve_run_readiness(diagram: Mapping[str, Any]) -> Dict[str, Any]:
    """Internal helper to resolve the run readiness."""
    input_node = _boundary_node(diagram, "input")
    output_node = _boundary_node(diagram, "output")
    if not input_node or not output_node:
        raise MapExecutionError("Input and Output nodes are required.")

    input_edges = _outgoing_edges(diagram, str(input_node.get("id") or ""))
    output_edges = _incoming_edges(diagram, str(output_node.get("id") or ""))
    if len(input_edges) != 1:
        raise MapExecutionError(
            "Input must connect to exactly one downstream shape before the map can run."
            if input_edges
            else "Connect Input to one downstream shape before the map can run."
        )
    if not output_edges:
        raise MapExecutionError("Connect at least one upstream shape into Output before the map can run.")

    forward = _collect_reachable(diagram, str(input_node.get("id") or ""), "out")
    if str(output_node.get("id") or "") not in forward:
        raise MapExecutionError("Create a connected path from Input to Output before running.")
    backward = _collect_reachable(diagram, str(output_node.get("id") or ""), "in")
    relevant_ids = set(node_id for node_id in forward if node_id in backward)

    nodes_by_id = {str(node.get("id") or ""): dict(node) for node in (diagram.get("nodes") or [])}
    for node_id in relevant_ids:
        node = nodes_by_id.get(node_id) or {}
        if not _is_branch_node(node):
            continue
        expression = str(node.get("conditionExpression") or "").strip()
        if not expression:
            raise MapExecutionError(f"{str(node.get('title') or node_id)} needs a Python boolean expression before it can route Yes and No.")
        counts = _branch_connection_counts(diagram, node_id, relevant_ids=relevant_ids)
        if counts["input"] < 1 or counts["yes"] < 1 or counts["no"] < 1:
            raise MapExecutionError(
                f"{str(node.get('title') or node_id)} needs at least one inbound, one Yes, and one No connection."
            )

    return {
        "input_node": input_node,
        "output_node": output_node,
        "relevant_ids": relevant_ids,
        "execution_order": _topological_order(diagram, relevant_ids=relevant_ids),
    }


def _node_runtime_parameters(
    node: Mapping[str, Any],
    *,
    extra_parameters: Mapping[str, Any],
    node_parameters: Mapping[str, Any],
) -> Dict[str, Any]:
    """Internal helper for node runtime parameters."""
    merged: Dict[str, Any] = {}
    if str(node.get("paramsText") or "").strip():
        merged = _merge_structured_data(merged, _parse_json_object(node.get("paramsText"), label=f"Node params for {node.get('title') or node.get('id') or 'node'}"))
    if extra_parameters:
        merged = _merge_structured_data(merged, dict(extra_parameters))
    node_id = str(node.get("id") or "").strip()
    node_title = str(node.get("title") or "").strip()
    for key in (node_id, node_title):
        if key and isinstance(node_parameters.get(key), Mapping):
            merged = _merge_structured_data(merged, dict(node_parameters.get(key) or {}))
    return merged


def _coerce_response_payload(response: Any) -> tuple[int, Dict[str, Any]]:
    """Internal helper to coerce the response payload."""
    if isinstance(response, Mapping):
        return 200, dict(response)
    status_code = int(getattr(response, "status_code", 200) or 200)
    payload: Dict[str, Any] = {}
    if hasattr(response, "json"):
        try:
            parsed = response.json()
            if isinstance(parsed, Mapping):
                payload = dict(parsed)
        except Exception:
            payload = {}
    return status_code, payload


def _run_plaza_pulser_request(
    *,
    plaza_url: str,
    request_payload: Dict[str, Any],
    request_post: RequestPost,
    timeout_sec: float,
) -> Dict[str, Any]:
    """Internal helper to run the Plaza pulser request."""
    try:
        response = request_post(
            f"{normalize_plaza_url(plaza_url)}/api/pulsers/test",
            json=request_payload,
            timeout=max(float(timeout_sec or 0.0), 0.1),
        )
    except Exception as exc:
        raise MapExecutionError(f"Pulser execution failed while contacting Plaza at {plaza_url}: {exc}") from exc

    status_code, payload = _coerce_response_payload(response)
    if status_code >= 400:
        raise MapExecutionError(
            str(payload.get("detail") or payload.get("message") or "Pulser execution failed.")
        )
    if not payload:
        payload = {"status": "success", "result": {}}
    payload.setdefault("status", "success")
    return payload


def execute_map_phema(
    phema: Mapping[str, Any],
    *,
    input_data: Any = None,
    extra_parameters: Mapping[str, Any] | None = None,
    node_parameters: Mapping[str, Any] | None = None,
    plaza_url: str = "",
    request_post: RequestPost | None = None,
    timeout_sec: float = 30.0,
) -> Dict[str, Any]:
    """Handle execute map phema."""
    diagram = _diagram_from_phema(phema)
    readiness = _resolve_run_readiness(diagram)
    normalized_plaza_url = normalize_plaza_url(
        plaza_url or diagram.get("plazaUrl") or phema.get("plaza_url") or phema.get("plazaUrl") or ""
    )
    initial_input = _coerce_mapping(input_data if input_data is not None else {}, label="Map input")
    shared_parameters = _coerce_mapping(extra_parameters, label="extra_parameters")
    per_node_parameters = _coerce_mapping(node_parameters, label="node_parameters")
    request_post_fn = request_post or requests.post

    nodes_by_id = {str(node.get("id") or ""): dict(node) for node in (diagram.get("nodes") or [])}
    step_outputs: Dict[str, Any] = {}
    active_branch_edge_ids: set[str] = set()
    steps: List[Dict[str, Any]] = []
    started_at = _utcnow_iso()

    input_node = readiness["input_node"]
    output_node = readiness["output_node"]
    step_outputs[str(input_node.get("id") or "")] = _clone(initial_input)
    steps.append(
        {
            "kind": "input",
            "node_id": str(input_node.get("id") or ""),
            "title": str(input_node.get("title") or "Input"),
            "status": "ready",
            "input": _clone(initial_input),
            "output": _clone(initial_input),
            "pulse_name": "",
            "pulser_name": "",
            "error": "",
        }
    )

    for node in readiness["execution_order"]:
        node_id = str(node.get("id") or "")
        connected_incoming_edges = [
            edge
            for edge in _incoming_edges(diagram, node_id)
            if str(edge.get("from") or "") in readiness["relevant_ids"]
        ]
        incoming_edges = [
            edge
            for edge in connected_incoming_edges
            if _edge_has_active_payload(edge, nodes_by_id, step_outputs, active_branch_edge_ids)
        ]

        node_input: Dict[str, Any] = {}
        for edge in incoming_edges:
            patch = _build_mapped_edge_payload(step_outputs.get(str(edge.get("from") or "")), node, edge)
            node_input = _merge_structured_data(node_input, patch)

        branch_input_ready = not _is_branch_node(node) or _branch_input_ready(
            node,
            active_incoming_edges=incoming_edges,
            connected_incoming_edges=connected_incoming_edges,
        )
        if not incoming_edges or not branch_input_ready:
            steps.append(
                {
                    "kind": "branch" if _is_branch_node(node) else "node",
                    "node_id": node_id,
                    "title": str(node.get("title") or node_id),
                    "status": "skipped",
                    "input": _clone(node_input),
                    "output": None,
                    "pulse_name": str(node.get("pulseName") or ""),
                    "pulser_name": str(node.get("pulserName") or ""),
                    "error": (
                        "Waiting for all inbound branch connections before evaluating this branch."
                        if _is_branch_node(node) and connected_incoming_edges and _branch_connector_mode(node, "input") == "all"
                        else ""
                    ),
                }
            )
            continue

        runtime_parameters = _node_runtime_parameters(
            node,
            extra_parameters=shared_parameters,
            node_parameters=per_node_parameters,
        )
        if runtime_parameters:
            node_input = _merge_structured_data(node_input, runtime_parameters)

        if _is_branch_node(node):
            try:
                branch_decision = evaluate_branch_condition(str(node.get("conditionExpression") or ""), node_input)
            except Exception as exc:
                raise MapExecutionError(
                    f"{str(node.get('title') or node_id)} branch condition failed: {exc}"
                ) from exc
            selected_route = "yes" if branch_decision else "no"
            branch_output = _clone(node_input)
            step_outputs[node_id] = branch_output
            route_edges = _active_branch_route_edges(
                node,
                [
                    edge
                    for edge in _outgoing_edges(diagram, node_id)
                    if str(edge.get("to") or "") in readiness["relevant_ids"]
                ],
                selected_route,
            )
            active_route_edge_ids = {str(edge.get("id") or "") for edge in route_edges}
            for edge in _outgoing_edges(diagram, node_id):
                if str(edge.get("to") or "") not in readiness["relevant_ids"]:
                    continue
                edge_id = str(edge.get("id") or "")
                if edge_id in active_route_edge_ids:
                    active_branch_edge_ids.add(edge_id)
                else:
                    active_branch_edge_ids.discard(edge_id)
            steps.append(
                {
                    "kind": "branch",
                    "node_id": node_id,
                    "title": str(node.get("title") or node_id),
                    "status": "ready",
                    "input": _clone(node_input),
                    "output": branch_output,
                    "condition_expression": str(node.get("conditionExpression") or ""),
                    "selected_route": selected_route,
                    "pulse_name": "",
                    "pulser_name": "",
                    "error": "",
                }
            )
            continue

        pulse_name = str(node.get("pulseName") or "").strip()
        pulse_address = str(node.get("pulseAddress") or "").strip()
        pulser_id = str(node.get("pulserId") or "").strip()
        pulser_name = str(node.get("pulserName") or "").strip()
        pulser_address = str(node.get("pulserAddress") or "").strip()
        practice_id = str(node.get("practiceId") or "get_pulse_data").strip() or "get_pulse_data"
        if not (pulse_name or pulse_address) or not (pulser_id or pulser_name or pulser_address):
            raise MapExecutionError(f"{str(node.get('title') or node_id)} needs both a pulse and an active pulser to run.")

        request_payload = {
            "pulser_id": pulser_id,
            "pulser_name": pulser_name,
            "pulser_address": pulser_address,
            "practice_id": practice_id,
            "pulse_name": pulse_name,
            "pulse_address": pulse_address,
            "output_schema": dict(node.get("outputSchema") or {}) if isinstance(node.get("outputSchema"), Mapping) else {},
            "input": _clone(node_input),
        }
        payload = _run_plaza_pulser_request(
            plaza_url=normalized_plaza_url,
            request_payload=request_payload,
            request_post=request_post_fn,
            timeout_sec=timeout_sec,
        )
        node_output = payload.get("result") if isinstance(payload, Mapping) and "result" in payload else payload
        step_outputs[node_id] = _clone(node_output)
        steps.append(
            {
                "kind": "node",
                "node_id": node_id,
                "title": str(node.get("title") or node_id),
                "status": "ready",
                "input": _clone(node_input),
                "output": _clone(node_output),
                "pulse_name": pulse_name,
                "pulser_name": pulser_name,
                "error": "",
            }
        )

    output_payload: Dict[str, Any] = {}
    output_incoming_edges = [
        edge
        for edge in _incoming_edges(diagram, str(output_node.get("id") or ""))
        if str(edge.get("from") or "") in readiness["relevant_ids"]
        and _edge_has_active_payload(edge, nodes_by_id, step_outputs, active_branch_edge_ids)
    ]
    if not output_incoming_edges:
        raise MapExecutionError("The active diagram path did not reach Output.")
    for edge in output_incoming_edges:
        patch = _build_mapped_edge_payload(step_outputs.get(str(edge.get("from") or "")), output_node, edge)
        output_payload = _merge_structured_data(output_payload, patch)

    step_outputs[str(output_node.get("id") or "")] = _clone(output_payload)
    steps.append(
        {
            "kind": "output",
            "node_id": str(output_node.get("id") or ""),
            "title": str(output_node.get("title") or "Output"),
            "status": "ready",
            "input": _clone(output_payload),
            "output": _clone(output_payload),
            "pulse_name": "",
            "pulser_name": "",
            "error": "",
        }
    )

    return {
        "status": "success",
        "phema_id": str(phema.get("phema_id") or phema.get("id") or ""),
        "phema_name": str(phema.get("name") or "Untitled Map Phema"),
        "plaza_url": normalized_plaza_url,
        "input": _clone(initial_input),
        "output": _clone(output_payload),
        "steps": steps,
        "started_at": started_at,
        "finished_at": _utcnow_iso(),
        "step_count": len(steps),
    }


__all__ = [
    "MapExecutionError",
    "execute_map_phema",
]
