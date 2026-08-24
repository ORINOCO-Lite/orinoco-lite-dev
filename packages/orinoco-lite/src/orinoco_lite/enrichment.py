"""Companion-aware use of the pinned Things enrichment helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Any

from linkml_runtime import SchemaView
from things_enrichment_tools import (
    update_data_property as _upstream_update_data_property,
    update_multivalued_object_property as _upstream_update_multivalued_object_property,
    update_object_property as _upstream_update_object_property,
)

from .annotations import (
    compact_enrichment_view,
    split_enrichment_view,
)
from .errors import ConfigurationError


ATTRIBUTE_SPECIFICATION = "dlthings:AttributeSpecification"


@dataclass(frozen=True)
class EnrichmentUpdate:
    """Detached canonical state returned by one ownership-aware update."""

    record: dict[str, Any]
    companion: dict[str, object] | None
    modified: bool


@dataclass(frozen=True)
class EnrichmentSlotSemantics:
    """Locked-schema representation of one topical data-property slot."""

    predicate: str
    class_range: bool
    datatype: str | None = None


def _line(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\n" in value
        or "\r" in value
        or "\0" in value
    ):
        raise ConfigurationError(f"{label} must be a non-empty single line")
    return value


def _machine_identity(owner_id: object, source_id: object) -> tuple[str, str]:
    return (
        _line(owner_id, "Enrichment owner ID"),
        _line(source_id, "Enrichment source ID"),
    )


def resolve_enrichment_slot(
    schema: SchemaView,
    topical_slot: str,
) -> EnrichmentSlotSemantics:
    """Resolve one supported topical slot from the pinned LinkML schema."""

    topical_slot = _line(topical_slot, "Qualified data topical slot")
    if not isinstance(schema, SchemaView):
        raise ConfigurationError("Enrichment schema must be a LinkML SchemaView")
    try:
        slot = schema.get_slot(topical_slot)
        if slot is None or not slot.range:
            raise ConfigurationError(
                f"Locked schema has no range for topical slot {topical_slot}"
            )
        predicate = _line(
            str(schema.get_uri(topical_slot, expand=False)),
            f"Predicate for topical slot {topical_slot}",
        )
        if ":" not in predicate:
            raise ConfigurationError(
                f"Locked schema predicate for topical slot {topical_slot} "
                "must be a CURIE"
            )
        if schema.get_class(slot.range) is not None:
            return EnrichmentSlotSemantics(predicate, class_range=True)
        range_type = schema.get_type(slot.range)
        if range_type is None or range_type.uri is None or range_type.base is None:
            raise ConfigurationError(
                f"Locked schema has no datatype for topical slot {topical_slot}"
            )
        datatype = _line(
            str(range_type.uri),
            f"Datatype for topical slot {topical_slot}",
        )
        if ":" not in datatype:
            raise ConfigurationError(
                f"Locked schema datatype for topical slot {topical_slot} "
                "must be a CURIE"
            )
    except ConfigurationError:
        raise
    except Exception as error:
        raise ConfigurationError(
            f"Could not resolve topical slot {topical_slot} from the locked schema"
        ) from error

    # String-backed LinkML values remain direct strings in both the topical
    # slot and its qualified assertion.  A range is needed only for the local
    # lexical bridge around native non-string values.
    if str(range_type.base) in {"str", "URIorCURIE"}:
        datatype = None
    return EnrichmentSlotSemantics(
        predicate,
        class_range=False,
        datatype=datatype,
    )


def _preserved_empty_companion(
    companion: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if companion is None or companion.get("assertions") != []:
        return None
    return deepcopy(dict(companion))


def _result(
    baseline_record: Mapping[str, Any],
    baseline_companion: Mapping[str, object] | None,
    working: Mapping[str, Any],
    upstream_modified: bool,
) -> EnrichmentUpdate:
    record, companion = split_enrichment_view(working)
    if companion is None:
        companion = _preserved_empty_companion(baseline_companion)
    modified = (
        record != dict(baseline_record)
        or companion
        != (dict(baseline_companion) if baseline_companion is not None else None)
    )
    if modified != upstream_modified:
        raise ConfigurationError(
            "Pinned enrichment helper modification result disagrees with the "
            "split canonical state"
        )
    return EnrichmentUpdate(record, companion, modified)


def _collection(
    working: dict[str, Any], collection_slot: str
) -> list[dict[str, Any]]:
    raw = working.get(collection_slot, [])
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ConfigurationError(
            f"Enrichment collection {collection_slot} must be a list of mappings"
        )
    return raw


def _json_lexical(value: object) -> str:
    if value is None or isinstance(value, (str, list, dict)):
        raise ConfigurationError(
            "Typed qualified data values must be non-string JSON scalars"
        )
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "Typed qualified data value has no canonical JSON lexical form"
        ) from error


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported constant {value}")


def _native_json_scalar(value: object) -> object:
    if not isinstance(value, str):
        raise ConfigurationError(
            "Stored typed qualified data value must use a string lexical form"
        )
    try:
        native = json.loads(
            value,
            parse_constant=_reject_json_constant,
        )
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "Stored typed qualified data value is not canonical JSON"
        ) from error
    if _json_lexical(native) != value:
        raise ConfigurationError(
            "Stored typed qualified data value is not in canonical lexical form"
        )
    return native


def _typed_values(value: Any, datatype: str | None) -> None:
    values = value if isinstance(value, list) else [value]
    if any(item is None for item in values):
        raise ConfigurationError("Qualified data values cannot be null")
    if not values:
        if datatype is not None and ":" not in _line(
            datatype, "Qualified data datatype"
        ):
            raise ConfigurationError("Qualified data datatype must be a CURIE")
        return

    if all(isinstance(item, str) for item in values):
        if datatype is not None:
            raise ConfigurationError(
                "String qualified data values must not declare a datatype range"
            )
        return

    if datatype is None:
        raise ConfigurationError(
            "Non-string qualified data values require an explicit locked datatype"
        )
    if ":" not in _line(datatype, "Qualified data datatype"):
        raise ConfigurationError("Qualified data datatype must be a CURIE")
    for item in values:
        _json_lexical(item)


def _prepare_typed_attributes(
    working: dict[str, Any],
    *,
    collection_slot: str,
    predicate_key: str,
    predicate: str,
    value_key: str,
    datatype: str | None,
) -> dict[int, str]:
    if datatype is None:
        return {}
    originals: dict[int, str] = {}
    for assertion in _collection(working, collection_slot):
        if (
            assertion.get(predicate_key) != predicate
            or assertion.get("range") != datatype
        ):
            continue
        lexical = assertion.get(value_key)
        native = _native_json_scalar(lexical)
        originals[id(assertion)] = lexical
        assertion[value_key] = native
    return originals


def _normalize_data_assertions(
    working: dict[str, Any],
    *,
    collection_slot: str,
    predicate_key: str,
    predicate: str,
    value_key: str,
    datatype: str | None,
    original_ids: set[int],
    typed_originals: Mapping[int, str],
) -> None:
    for assertion in _collection(working, collection_slot):
        assertion_id = id(assertion)
        if assertion_id in typed_originals:
            assertion[value_key] = typed_originals[assertion_id]
            continue
        if assertion_id in original_ids or assertion.get(predicate_key) != predicate:
            continue
        if collection_slot == "attributes" and value_key == "value":
            assertion["schema_type"] = ATTRIBUTE_SPECIFICATION
            if datatype is not None:
                assertion[value_key] = _json_lexical(assertion.get(value_key))
                assertion["range"] = datatype


def update_data_property(
    record: Mapping[str, Any],
    companion: Mapping[str, object] | None,
    *,
    predicate: str,
    value: Any,
    topical_slot: str | None = None,
    owner_id: str,
    source_id: str,
    collection_slot: str = "attributes",
    value_key: str = "value",
    predicate_key: str = "predicate",
    valid_owner_ids: list[str | None] | None = None,
    datatype: str | None = None,
) -> EnrichmentUpdate:
    """Run pinned ``update_data_property`` and split its compact PAV.

    ``datatype`` is required for a native non-string source value.  The
    transient helper view uses the native value for exact upstream matching;
    the stored ``AttributeSpecification`` uses its canonical JSON lexical form
    and the locked LinkML datatype.
    """

    owner_id, source_id = _machine_identity(owner_id, source_id)
    predicate = _line(predicate, "Qualified data predicate")
    collection_slot = _line(collection_slot, "Qualified data collection slot")
    value_key = _line(value_key, "Qualified data value key")
    predicate_key = _line(predicate_key, "Qualified data predicate key")
    if topical_slot is not None:
        topical_slot = _line(topical_slot, "Qualified data topical slot")
    _typed_values(value, datatype)

    working = compact_enrichment_view(record, companion)
    initial_collection = _collection(working, collection_slot)
    original_ids = {id(item) for item in initial_collection}
    typed_originals = _prepare_typed_attributes(
        working,
        collection_slot=collection_slot,
        predicate_key=predicate_key,
        predicate=predicate,
        value_key=value_key,
        datatype=datatype,
    )
    upstream_modified = _upstream_update_data_property(
        working,
        predicate=predicate,
        value=deepcopy(value),
        collection_slot=collection_slot,
        value_key=value_key,
        topical_slot=topical_slot,
        owner_id=owner_id,
        source_id=source_id,
        predicate_key=predicate_key,
        valid_owner_ids=(
            deepcopy(valid_owner_ids) if valid_owner_ids is not None else None
        ),
    )
    _normalize_data_assertions(
        working,
        collection_slot=collection_slot,
        predicate_key=predicate_key,
        predicate=predicate,
        value_key=value_key,
        datatype=datatype,
        original_ids=original_ids,
        typed_originals=typed_originals,
    )
    return _result(record, companion, working, upstream_modified)


def update_schema_data_property(
    record: Mapping[str, Any],
    companion: Mapping[str, object] | None,
    *,
    schema: SchemaView,
    topical_slot: str,
    value: Any,
    owner_id: str,
    source_id: str,
    valid_owner_ids: list[str | None] | None = None,
    populate_topical: bool = True,
) -> EnrichmentUpdate:
    """Update one topical property using only locked-schema slot semantics.

    The schema supplies the predicate, class-range routing, and any datatype
    used by the native-to-lexical storage bridge.  The value's Python type is
    never used to choose a datatype.
    """

    if not isinstance(populate_topical, bool):
        raise ConfigurationError("populate_topical must be Boolean")
    if not populate_topical and value != []:
        raise ConfigurationError(
            "populate_topical may be disabled only for an empty source update"
        )
    semantics = resolve_enrichment_slot(schema, topical_slot)
    helper_topical_slot = topical_slot if populate_topical else None
    if semantics.class_range:
        return update_data_property(
            record,
            companion,
            predicate=semantics.predicate,
            value=value,
            collection_slot="characterized_by",
            value_key="object",
            topical_slot=helper_topical_slot,
            owner_id=owner_id,
            source_id=source_id,
            valid_owner_ids=valid_owner_ids,
        )
    return update_data_property(
        record,
        companion,
        predicate=semantics.predicate,
        value=value,
        topical_slot=helper_topical_slot,
        owner_id=owner_id,
        source_id=source_id,
        valid_owner_ids=valid_owner_ids,
        datatype=semantics.datatype,
    )


def update_object_property(
    record: Mapping[str, Any],
    companion: Mapping[str, object] | None,
    *,
    slot: str,
    value: Mapping[str, Any] | None,
    owner_id: str,
    source_id: str,
    valid_owner_ids: list[str | None] | None = None,
) -> EnrichmentUpdate:
    """Run pinned ``update_object_property`` and split its compact PAV."""

    owner_id, source_id = _machine_identity(owner_id, source_id)
    slot = _line(slot, "Object-property slot")
    working = compact_enrichment_view(record, companion)
    upstream_modified = _upstream_update_object_property(
        working,
        slot=slot,
        value=deepcopy(dict(value)) if value is not None else None,
        owner_id=owner_id,
        source_id=source_id,
        valid_owner_ids=(
            deepcopy(valid_owner_ids) if valid_owner_ids is not None else None
        ),
    )
    return _result(record, companion, working, upstream_modified)


def update_multivalued_object_property(
    record: Mapping[str, Any],
    companion: Mapping[str, object] | None,
    *,
    slot: str,
    values: Sequence[Mapping[str, Any]] | None,
    owner_id: str,
    source_id: str,
    valid_owner_ids: list[str | None] | None = None,
) -> EnrichmentUpdate:
    """Run pinned multivalued-object update and split its compact PAV."""

    owner_id, source_id = _machine_identity(owner_id, source_id)
    slot = _line(slot, "Multivalued object-property slot")
    copied_values = (
        [deepcopy(dict(value)) for value in values] if values is not None else None
    )
    working = compact_enrichment_view(record, companion)
    upstream_modified = _upstream_update_multivalued_object_property(
        working,
        slot=slot,
        values=copied_values,
        owner_id=owner_id,
        source_id=source_id,
        valid_owner_ids=(
            deepcopy(valid_owner_ids) if valid_owner_ids is not None else None
        ),
    )
    return _result(record, companion, working, upstream_modified)
