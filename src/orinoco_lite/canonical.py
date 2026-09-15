"""Canonical mapping order and YAML serialization for semantic metadata."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, cast

from dump_things_service.utils import json2yaml, order_dict
import yaml


def _strict_json_value(value: Any) -> Any:
    """Return detached JSON data without accepting Python-only extensions."""

    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Canonical JSON mapping keys must be strings")
        return {key: _strict_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_strict_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(
        "Canonical JSON values must contain only mappings, lists, and scalars"
    )


def canonical_json(value: Any) -> str:
    """Serialize strict JSON with stable keys, Unicode, and list order."""

    return json.dumps(
        _strict_json_value(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 JSON representation used for hashing."""

    return canonical_json(value).encode("utf-8")


def canonical_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursively key-sorted copy while preserving list order.

    Dump Things owns the ordering behavior.  This wrapper gives every Orinoco
    metadata writer one small shared entry point without copying that logic.
    """

    if not isinstance(value, Mapping):
        raise TypeError("Canonical metadata must be a mapping")
    return cast(dict[str, Any], order_dict(dict(value)))


def canonical_yaml(value: Mapping[str, Any]) -> str:
    """Serialize one mapping exactly like the pinned Dump Things helpers."""

    return json2yaml(canonical_mapping(value))


def canonical_yaml_bytes(value: Mapping[str, Any]) -> bytes:
    """Return the canonical UTF-8 representation used for repository files."""

    return canonical_yaml(value).encode("utf-8")


def canonicalize_yaml_text(text: str) -> str:
    """Normalize one YAML mapping through the shared canonicalizer."""

    value = yaml.safe_load(text)
    if not isinstance(value, Mapping):
        raise TypeError("Canonical metadata YAML must contain a mapping")
    return canonical_yaml(value)
