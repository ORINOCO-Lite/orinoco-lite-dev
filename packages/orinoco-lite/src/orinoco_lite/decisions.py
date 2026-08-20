"""Compact current-state decisions for source-adapter candidates.

Git and GitHub retain review history.  This module stores only the current
per-PID decisions and the authenticated GitHub comment blocks they reference.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

import yaml

from .candidates import Candidate, CandidatePlan
from .canonical import canonical_json_bytes, canonical_yaml_bytes
from .errors import ConfigurationError


DECISION_CACHE_FORMAT = "orinoco-lite-curation-decisions-v1"

_CLAIM_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_COMMENT_REFERENCE = re.compile(r"github-comment:([1-9][0-9]*)\Z")
_REVIEWED_AT = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z"
)
_SAFE_PATH_SEGMENT = re.compile(r"[A-Za-z0-9._~-]+\Z")
_REVIEW_URL = re.compile(
    r"https://github\.com/([^/]+?)/([^/]+?)/pull/([1-9][0-9]*)"
    r"#issuecomment-([1-9][0-9]*)\Z"
)
_REVIEWER_URL = re.compile(r"https://github\.com/([^/]+)\Z")


class Disposition(StrEnum):
    """The complete supported decision vocabulary."""

    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"


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


def _strict_fields(
    value: object,
    fields: frozenset[str],
    label: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{label} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise ConfigurationError(f"{label} field names must be strings")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ConfigurationError(f"{label} has invalid fields: {'; '.join(details)}")
    return value


def _source_coordinate(value: object, label: str) -> bytes:
    if not isinstance(value, Mapping) or not value:
        raise ConfigurationError(f"{label} must be a non-empty mapping")
    try:
        encoded = canonical_json_bytes(value)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"{label} must contain strict JSON: {error}") from error
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict) or not decoded:  # pragma: no cover - guarded
        raise AssertionError("source coordinate did not decode to a mapping")
    return encoded


def _safe_segment(value: str, label: str) -> str:
    if (
        _SAFE_PATH_SEGMENT.fullmatch(value) is None
        or value in {".", ".."}
    ):
        raise ConfigurationError(f"{label} must be one safe GitHub path segment")
    return value


def _comment_id(reference: object) -> str:
    rendered = _line(reference, "Decision review reference")
    match = _COMMENT_REFERENCE.fullmatch(rendered)
    if match is None:
        raise ConfigurationError(
            "Decision review reference must be github-comment:<positive decimal id>"
        )
    return match.group(1)


def _reviewer_url(value: object) -> str:
    rendered = _line(value, "Review reviewer")
    match = _REVIEWER_URL.fullmatch(rendered)
    if match is None:
        raise ConfigurationError(
            "Review reviewer must be an exact https://github.com/<event-login> URL"
        )
    _safe_segment(match.group(1), "Review event login")
    return rendered


def _review_url(value: object) -> tuple[str, str]:
    rendered = _line(value, "Review URL")
    match = _REVIEW_URL.fullmatch(rendered)
    if match is None:
        raise ConfigurationError(
            "Review URL must be an exact public GitHub pull-request comment URL"
        )
    _safe_segment(match.group(1), "Review repository owner")
    _safe_segment(match.group(2), "Review repository name")
    return rendered, match.group(4)


def _reviewed_at(value: object) -> str:
    rendered = _line(value, "Review time")
    if _REVIEWED_AT.fullmatch(rendered) is None:
        raise ConfigurationError(
            "Review time must be canonical UTC seconds (YYYY-MM-DDTHH:MM:SSZ)"
        )
    try:
        parsed = datetime.strptime(rendered, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ConfigurationError(f"Review time is invalid: {rendered}") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != rendered:
        raise ConfigurationError(
            "Review time must be canonical UTC seconds (YYYY-MM-DDTHH:MM:SSZ)"
        )
    return rendered


@dataclass(frozen=True, init=False)
class Review:
    """One authenticated GitHub comment event referenced by current decisions."""

    reviewer: str
    reviewed_at: str
    review_url: str
    _source_coordinate_json: bytes = field(repr=False)

    def __init__(
        self,
        *,
        source_coordinate: Mapping[str, object],
        reviewer: str,
        reviewed_at: str,
        review_url: str,
    ) -> None:
        coordinate = _source_coordinate(source_coordinate, "Review source coordinate")
        canonical_reviewer = _reviewer_url(reviewer)
        canonical_time = _reviewed_at(reviewed_at)
        canonical_url, _ = _review_url(review_url)
        object.__setattr__(self, "_source_coordinate_json", coordinate)
        object.__setattr__(self, "reviewer", canonical_reviewer)
        object.__setattr__(self, "reviewed_at", canonical_time)
        object.__setattr__(self, "review_url", canonical_url)

    @property
    def source_coordinate(self) -> dict[str, object]:
        """Return a detached strict-JSON source coordinate."""

        decoded = json.loads(self._source_coordinate_json)
        if not isinstance(decoded, dict):  # pragma: no cover - constructor guard
            raise AssertionError("review source coordinate is not a mapping")
        return decoded

    def to_mapping(self) -> dict[str, object]:
        """Return the exact v1 review mapping."""

        return {
            "source_coordinate": self.source_coordinate,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "review_url": self.review_url,
        }


@dataclass(frozen=True)
class Decision:
    """One current source-record decision, keyed by PID in the cache."""

    source_record_id: str
    claim_sha256: str
    disposition: Disposition | str
    review: str

    def __post_init__(self) -> None:
        source_id = _line(self.source_record_id, "Decision source record ID")
        claim = _line(self.claim_sha256, "Decision claim digest")
        if _CLAIM_SHA256.fullmatch(claim) is None:
            raise ConfigurationError(
                "Decision claim digest must use lowercase sha256:<64 hex> form"
            )
        try:
            disposition = Disposition(self.disposition)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                "Decision disposition must be accept, reject, or defer"
            ) from error
        review = _line(self.review, "Decision review reference")
        _comment_id(review)
        object.__setattr__(self, "source_record_id", source_id)
        object.__setattr__(self, "claim_sha256", claim)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "review", review)

    def to_mapping(self) -> dict[str, str]:
        """Return the exact v1 decision mapping."""

        return {
            "source_record_id": self.source_record_id,
            "claim_sha256": self.claim_sha256,
            "disposition": self.disposition.value,
            "review": self.review,
        }


@dataclass(frozen=True)
class DecisionCache:
    """Validated compact current state for one adapter."""

    adapter: str
    reviews: Mapping[str, Review] = field(default_factory=dict)
    decisions: Mapping[str, Decision] = field(default_factory=dict)

    def __post_init__(self) -> None:
        adapter = _line(self.adapter, "Decision-cache adapter")
        if not isinstance(self.reviews, Mapping):
            raise ConfigurationError("Decision-cache reviews must be a mapping")
        if not isinstance(self.decisions, Mapping):
            raise ConfigurationError("Decision-cache decisions must be a mapping")

        reviews: dict[str, Review] = {}
        for reference, review in self.reviews.items():
            comment_id = _comment_id(reference)
            if not isinstance(review, Review):
                raise ConfigurationError("Decision-cache reviews must contain Reviews")
            _, url_comment_id = _review_url(review.review_url)
            if comment_id != url_comment_id:
                raise ConfigurationError(
                    "Review URL comment id does not match its review reference"
                )
            reviews[reference] = review

        decisions: dict[str, Decision] = {}
        source_ids: set[str] = set()
        for pid, decision in self.decisions.items():
            canonical_pid = _line(pid, "Decision PID")
            if not isinstance(decision, Decision):
                raise ConfigurationError(
                    "Decision-cache decisions must contain Decisions"
                )
            if decision.source_record_id in source_ids:
                raise ConfigurationError(
                    "Decision cache repeats a source record identity"
                )
            source_ids.add(decision.source_record_id)
            decisions[canonical_pid] = decision

        referenced = {decision.review for decision in decisions.values()}
        missing = referenced - set(reviews)
        if missing:
            raise ConfigurationError(
                "Decision references missing reviews: " + ", ".join(sorted(missing))
            )
        unreferenced = set(reviews) - referenced
        if unreferenced:
            raise ConfigurationError(
                "Decision cache retains unreferenced reviews: "
                + ", ".join(sorted(unreferenced))
            )

        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(
            self, "reviews", MappingProxyType(dict(sorted(reviews.items())))
        )
        object.__setattr__(
            self, "decisions", MappingProxyType(dict(sorted(decisions.items())))
        )

    @classmethod
    def empty(cls, adapter: str) -> DecisionCache:
        """Create the valid missing-file state for one literal adapter."""

        return cls(adapter=adapter)

    def to_mapping(self) -> dict[str, object]:
        """Return the exact v1 cache mapping."""

        return {
            "format": DECISION_CACHE_FORMAT,
            "adapter": self.adapter,
            "reviews": {
                reference: review.to_mapping()
                for reference, review in self.reviews.items()
            },
            "decisions": {
                pid: decision.to_mapping()
                for pid, decision in self.decisions.items()
            },
        }

    def is_suppressed(self, candidate: Candidate) -> bool:
        """Return whether an unchanged accept or reject suppresses a candidate."""

        if not isinstance(candidate, Candidate):
            raise ConfigurationError("Suppression requires a Candidate")
        decision = self.decisions.get(candidate.pid)
        return bool(
            decision is not None
            and decision.source_record_id == candidate.source_record_id
            and decision.claim_sha256 == candidate.claim_sha256
            and decision.disposition in {Disposition.ACCEPT, Disposition.REJECT}
        )

    def candidates_requiring_review(
        self, plan: CandidatePlan
    ) -> tuple[Candidate, ...]:
        """Return plan candidates not suppressed by current decisions."""

        _matching_plan(self, plan)
        return tuple(
            candidate
            for candidate in plan.candidates
            if not self.is_suppressed(candidate)
        )

    def updated(
        self,
        plan: CandidatePlan,
        dispositions: Mapping[str, Disposition | str],
        *,
        review_ref: str,
        source_coordinate: Mapping[str, object],
        reviewer: str,
        reviewed_at: str,
        review_url: str,
    ) -> DecisionCache:
        """Return current state after one complete authenticated review.

        ``plan`` is the active-decision-filtered proposal plan shown to the
        reviewer.  Its complete candidate set must have one submitted
        disposition each.  Candidate derivation can use
        :meth:`candidates_requiring_review` before constructing that plan.
        """

        _matching_plan(self, plan)
        if not plan.candidates:
            raise ConfigurationError("Cannot update decisions for an empty plan")
        submitted_coordinate = _source_coordinate(
            source_coordinate, "Submitted source coordinate"
        )
        planned_coordinate = _source_coordinate(
            plan.source_coordinate, "Candidate-plan source coordinate"
        )
        if submitted_coordinate != planned_coordinate:
            raise ConfigurationError(
                "Submitted source coordinate does not match the candidate plan"
            )
        if not isinstance(dispositions, Mapping):
            raise ConfigurationError("Review dispositions must be a PID mapping")
        candidate_by_pid = {candidate.pid: candidate for candidate in plan.candidates}
        if not all(isinstance(pid, str) for pid in dispositions):
            raise ConfigurationError("Review disposition PIDs must be strings")
        submitted_pids = set(dispositions)
        candidate_pids = set(candidate_by_pid)
        if submitted_pids != candidate_pids:
            missing = sorted(candidate_pids - submitted_pids)
            unknown = sorted(submitted_pids - candidate_pids)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unknown:
                details.append("unknown " + ", ".join(unknown))
            raise ConfigurationError(
                "Review dispositions do not match the complete candidate set: "
                + "; ".join(details)
            )

        reference = _line(review_ref, "Decision review reference")
        comment_id = _comment_id(reference)
        review = Review(
            source_coordinate=source_coordinate,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            review_url=review_url,
        )
        _, url_comment_id = _review_url(review.review_url)
        if comment_id != url_comment_id:
            raise ConfigurationError(
                "Review URL comment id does not match its review reference"
            )
        existing_review = self.reviews.get(reference)
        if existing_review is not None and existing_review != review:
            raise ConfigurationError(
                "An existing review reference has different authenticated details"
            )

        decisions = dict(self.decisions)
        reviewed_sources = {
            candidate.source_record_id for candidate in plan.candidates
        }
        for pid, decision in tuple(decisions.items()):
            if pid in candidate_pids or decision.source_record_id in reviewed_sources:
                del decisions[pid]
        for pid, candidate in candidate_by_pid.items():
            decisions[pid] = Decision(
                source_record_id=candidate.source_record_id,
                claim_sha256=candidate.claim_sha256,
                disposition=dispositions[pid],
                review=reference,
            )

        referenced_reviews = {decision.review for decision in decisions.values()}
        reviews = {
            key: value
            for key, value in self.reviews.items()
            if key in referenced_reviews
        }
        reviews[reference] = review
        return DecisionCache(
            adapter=self.adapter,
            reviews=reviews,
            decisions=decisions,
        )


def _matching_plan(cache: DecisionCache, plan: CandidatePlan) -> None:
    if not isinstance(plan, CandidatePlan):
        raise ConfigurationError("Decision-cache operation requires a CandidatePlan")
    if plan.adapter != cache.adapter:
        raise ConfigurationError(
            "Candidate-plan adapter does not match the decision cache"
        )


def _cache_from_mapping(value: object, *, adapter: str) -> DecisionCache:
    root = _strict_fields(
        value,
        frozenset({"format", "adapter", "reviews", "decisions"}),
        "Decision cache",
    )
    if root["format"] != DECISION_CACHE_FORMAT:
        raise ConfigurationError(
            f"Decision-cache format must be {DECISION_CACHE_FORMAT}"
        )
    stored_adapter = _line(root["adapter"], "Decision-cache adapter")
    if stored_adapter != adapter:
        raise ConfigurationError("Stored decision-cache adapter does not match")
    raw_reviews = root["reviews"]
    raw_decisions = root["decisions"]
    if not isinstance(raw_reviews, Mapping):
        raise ConfigurationError("Decision-cache reviews must be a mapping")
    if not isinstance(raw_decisions, Mapping):
        raise ConfigurationError("Decision-cache decisions must be a mapping")

    reviews: dict[str, Review] = {}
    for reference, raw_review in raw_reviews.items():
        _comment_id(reference)
        fields = _strict_fields(
            raw_review,
            frozenset({"source_coordinate", "reviewer", "reviewed_at", "review_url"}),
            f"Review {reference}",
        )
        reviews[reference] = Review(
            source_coordinate=fields["source_coordinate"],
            reviewer=fields["reviewer"],
            reviewed_at=fields["reviewed_at"],
            review_url=fields["review_url"],
        )

    decisions: dict[str, Decision] = {}
    for pid, raw_decision in raw_decisions.items():
        canonical_pid = _line(pid, "Decision PID")
        fields = _strict_fields(
            raw_decision,
            frozenset({"source_record_id", "claim_sha256", "disposition", "review"}),
            f"Decision {canonical_pid}",
        )
        decisions[canonical_pid] = Decision(
            source_record_id=fields["source_record_id"],
            claim_sha256=fields["claim_sha256"],
            disposition=fields["disposition"],
            review=fields["review"],
        )
    return DecisionCache(adapter=stored_adapter, reviews=reviews, decisions=decisions)


def serialize_decision_cache(cache: DecisionCache) -> bytes:
    """Serialize a validated cache as canonical YAML."""

    if not isinstance(cache, DecisionCache):
        raise ConfigurationError("Decision-cache serialization requires a cache")
    return canonical_yaml_bytes(cache.to_mapping())


def load_decision_cache(path: Path | str, *, adapter: str) -> DecisionCache:
    """Load exact canonical YAML, or return an empty cache when absent."""

    target = Path(path)
    if not target.exists():
        return DecisionCache.empty(adapter)
    try:
        raw = target.read_bytes()
        text = raw.decode("utf-8")
        value: Any = yaml.safe_load(text)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Cannot load decision cache {target}: {error}") from error
    cache = _cache_from_mapping(value, adapter=adapter)
    if serialize_decision_cache(cache) != raw:
        raise ConfigurationError(
            "Decision cache must use exact canonical YAML serialization"
        )
    return cache


def update_decision_cache(
    cache: DecisionCache,
    plan: CandidatePlan,
    dispositions: Mapping[str, Disposition | str],
    *,
    review_ref: str,
    source_coordinate: Mapping[str, object],
    reviewer: str,
    reviewed_at: str,
    review_url: str,
) -> DecisionCache:
    """Return the cache produced by one complete current-candidate review."""

    if not isinstance(cache, DecisionCache):
        raise ConfigurationError("Decision-cache update requires a cache")
    return cache.updated(
        plan,
        dispositions,
        review_ref=review_ref,
        source_coordinate=source_coordinate,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        review_url=review_url,
    )
