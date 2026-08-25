# Copyright 2026 Arista Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import json
import sys
from typing import Any

import yaml

from otgctl.methods import SKIP_METHODS


class _PermissiveLoader(yaml.SafeLoader):
    pass


def _unknown_tag(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)


_PermissiveLoader.add_multi_constructor("", _unknown_tag)


def _parse_value(key: str, raw: str) -> str | list[str]:
    """Parse a value string, using the key name to decide scalar vs list.

    Keys ending in "s" produce a list (even for a single value).
    Comma separates list elements.
    """
    if key.endswith("s"):
        return raw.split(",")
    if "," in raw:
        return raw.split(",")
    return raw


def _parse_leaf(segment: str) -> dict[str, str | list[str]]:
    """Parse the leaf segment of an API path into a dict.

    Supports multiple key=value pairs separated by semicolons,
    and comma-separated list values.

    Examples:
        'state=start'                          -> {'state': 'start'}
        'port_names=Ethernet1,Ethernet2'       -> {'port_names': ['Ethernet1', 'Ethernet2']}
        'port_names=Ethernet1;column_names=tx' -> {'port_names': ['Ethernet1'], 'column_names': ['tx']}
    """
    result = {}
    for pair in segment.split(";"):
        if "=" not in pair:
            raise ValueError(
                f"API path leaf must contain key=value pairs: {segment}")
        key, _, raw = pair.partition("=")
        if not key:
            raise ValueError(
                f"API path leaf contains an empty key: {segment}")
        if key in result:
            raise ValueError(
                f"API path leaf contains duplicate key '{key}': {segment}")
        result[key] = _parse_value(key, raw)
    return result


def parse_api_path(s: str) -> dict[str, Any]:
    """Convert an API path to a nested dict with choice keys.

    Examples:
        '//traffic/flow_transmit/state=start' becomes:
            {'choice': 'traffic', 'traffic': {'choice': 'flow_transmit',
             'flow_transmit': {'state': 'start'}}}

        '//port/port_names=Ethernet1,Ethernet2;column_names=tx' becomes:
            {'choice': 'port', 'port': {'port_names': ['Ethernet1', 'Ethernet2'],
             'column_names': ['tx']}}
    """
    s = s.lstrip("/")
    parts = s.split("/")

    if not parts or not parts[-1]:
        raise ValueError(f"Invalid API path: /{s}")
    if any(not part for part in parts):
        raise ValueError(f"Invalid API path with empty segment: /{s}")

    if "=" in parts[-1]:
        result = _parse_leaf(parts[-1])
        wrap = parts[:-1]
    else:
        result = {"choice": parts[-1]}
        wrap = parts[:-1]

    for part in reversed(wrap):
        result = {"choice": part, part: result}

    return result


def _parse_yaml_docs(text: str) -> list[Any]:
    """Parse potentially multi-document YAML text."""
    return list(yaml.load_all(text, Loader=_PermissiveLoader))


def _load_from_file(path: str) -> list[Any]:
    """Load data from a file path, returning a list of parsed documents."""
    with open(path) as f:
        text = f.read()

    if path.endswith(".json"):
        return [json.loads(text)]

    return _parse_yaml_docs(text)


def _load_from_stdin() -> list[Any]:
    """Load YAML data from stdin."""
    text = sys.stdin.read()
    return _parse_yaml_docs(text)


def _classify_doc(doc: Any, method_override: str | None) -> tuple[str, Any] | None:
    """Classify a parsed document and return (method, body).

    Type 1: has 'method' and 'request' keys -> use them
    Type 2: raw data -> needs method_override
    """
    if isinstance(doc, dict) and "method" in doc:
        method = doc["method"]
        if not isinstance(method, str) or not method.strip():
            raise ValueError(
                "Input 'method' must be a non-empty string.")
        if method in SKIP_METHODS:
            return None
        body = doc.get("request")
        return (method, body)

    if method_override:
        return (method_override, doc)

    raise ValueError(
        "Input has no 'method' key. Use -m to specify a method.")


def load_inputs(sources: list[str], method_override: str | None) -> list[tuple[str, Any]]:
    """Load all inputs and return list of (method_string, body) tuples.

    Each source is either:
      - A file path (YAML or JSON)
      - "-" for stdin
      - An API path like //a/b/key=value (leading //)
    """
    if not sources:
        if method_override:
            return [(method_override, None)]
        raise ValueError("No input sources provided.")

    results = []
    for source in sources:
        if source == "-":
            docs = _load_from_stdin()
        elif source.startswith("//"):
            body = parse_api_path(source)
            if not method_override:
                raise ValueError(
                    "API path input requires -m to specify a method.")
            results.append((method_override, body))
            continue
        else:
            docs = _load_from_file(source)

        if not docs:
            if method_override:
                docs = [None]
            else:
                raise ValueError(
                    "Input is empty. Use -m to specify a method for "
                    "a no-body request.")
        for doc in docs:
            if doc is None and not method_override:
                continue
            entry = _classify_doc(doc, method_override)
            if entry is not None:
                results.append(entry)

    return results
