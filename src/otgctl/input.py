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

from otgctl.methods import METHOD_MAP, OPERATION_ID_MAP, SKIP_METHODS


_TEXTPROTO_SUFFIXES = (".textproto", ".textpb", ".pbtxt")


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


def _textproto_method_name(method: str | None) -> str:
    """Return the gRPC method name used to select a textproto message."""
    if not method:
        raise ValueError(
            "Textproto input requires -m to specify a gRPC method name, "
            "for example -m SetConfig.")

    grpc_method = OPERATION_ID_MAP.get(method, method)
    if grpc_method not in METHOD_MAP:
        raise ValueError(
            f"Textproto input requires a supported gRPC method name; "
            f"got '{method}'.")
    return grpc_method


def _textproto_inner(text: str) -> str:
    """Accept textproto files that wrap the message in an outer brace pair.
    These may come from an ondatra log report."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped[1:-1]
    return text


def _parse_textproto(
    text: str, method: str | None, path: str,
) -> dict[str, Any] | None:
    """Parse a protobuf text-format request and convert it to a REST body.

    The gRPC request messages wrap the REST request in one top-level field,
    such as ``SetConfigRequest.config``.  REST receives the contents of that
    field, so unwrap a single-field request message here.
    """
    grpc_method = _textproto_method_name(method)

    try:
        from snappi import otg_pb2
        from google.protobuf import json_format, text_format
    except ImportError as e:
        raise ValueError(
            "Textproto input requires the optional 'snappi' dependency. "
            "Install it with: pip install 'otgctl[snappi]'.") from e

    message_type = getattr(otg_pb2, f"{grpc_method}Request", None)
    if message_type is None:
        # GetConfig and GetVersion use google.protobuf.Empty in the gRPC API.
        if grpc_method in {"GetConfig", "GetVersion"}:
            from google.protobuf.empty_pb2 import Empty
            message_type = Empty
        else:
            raise ValueError(
                f"snappi.otg_pb2 does not provide "
                f"{grpc_method}Request; installed snappi may be too old.")

    message = message_type()
    parse_text = _textproto_inner(text)
    try:
        text_format.Parse(parse_text, message)
    except text_format.ParseError as strict_error:
        # Older snappi releases can have a proto schema that does not know
        # fields introduced by newer releases.  Retry with a fresh message so
        # repeated fields from the first, failed parse are not retained.
        print(
            f"Warning: strict textproto parsing of {path} failed: "
            f"{strict_error}; "
            "retrying with unknown fields allowed.",
            file=sys.stderr,
        )
        message = message_type()
        try:
            text_format.Parse(parse_text, message, allow_unknown_field=True)
        except text_format.ParseError as relaxed_error:
            raise ValueError(
                f"Invalid textproto for {grpc_method}: {relaxed_error}"
            ) from strict_error

    fields = message.DESCRIPTOR.fields
    if not fields:
        return None

    body = json_format.MessageToDict(
        message, preserving_proto_field_name=True)
    if len(fields) == 1:
        return body.get(fields[0].name, {})
    return body


def _load_from_file(path: str, method_override: str | None) -> list[Any]:
    """Load data from a file path, returning a list of parsed documents."""
    with open(path) as f:
        text = f.read()

    if path.lower().endswith(_TEXTPROTO_SUFFIXES):
        return [_parse_textproto(text, method_override, path)]

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
            docs = _load_from_file(source, method_override)

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
