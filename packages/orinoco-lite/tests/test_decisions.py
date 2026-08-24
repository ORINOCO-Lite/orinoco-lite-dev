from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from orinoco_lite.candidates import Candidate, CandidatePlan
from orinoco_lite.canonical import canonical_yaml_bytes
from orinoco_lite.decisions import (
    DECISION_CACHE_FORMAT,
    Decision,
    DecisionCache,
    Disposition,
    Review,
    load_decision_cache,
    serialize_decision_cache,
    update_decision_cache,
)
from orinoco_lite.errors import ConfigurationError


ADAPTER = "example-adapter"
AGENT_PID = "xyzrins:source-adapters/example/v1"
BASE = "0123456789abcdef0123456789abcdef01234567"
NAMESPACE = "https://source.example/records"
COORDINATE = {"revision": "source-42"}
PID_ONE = "xyzrins:records/one"
PID_TWO = "xyzrins:records/two"


def record(pid: str, name: str) -> dict[str, object]:
    return {
        "schema_type": "xyzri:XYZOrganization",
        "pid": pid,
        "name": name,
    }


def candidate(
    source_id: str,
    pid: str,
    *,
    source_name: str,
    baseline_name: str = "baseline",
) -> Candidate:
    return Candidate(
        source_namespace=NAMESPACE,
        source_record_id=source_id,
        pid=pid,
        record_path=f"XYZOrganization/{source_id}.yaml",
        baseline_record=record(pid, baseline_name),
        proposed_record=record(pid, source_name),
        baseline_companion=None,
        proposed_companion=None,
        source_claim={"name": source_name},
    )


def plan(*candidates: Candidate, coordinate: object = COORDINATE) -> CandidatePlan:
    return CandidatePlan(
        adapter=ADAPTER,
        adapter_version="1.0.0",
        adapter_agent_pid=AGENT_PID,
        source_namespace=NAMESPACE,
        source_coordinate=coordinate,
        metadata_base=BASE,
        candidates=candidates,
    )


def review_details(
    comment_id: str = "123456",
    *,
    coordinate: object = COORDINATE,
) -> dict[str, object]:
    return {
        "review_ref": f"github-comment:{comment_id}",
        "source_coordinate": coordinate,
        "reviewer": "https://github.com/Reviewer-Name",
        "reviewed_at": "2026-08-20T18:42:00Z",
        "review_url": (
            f"https://github.com/con/site/pull/42#issuecomment-{comment_id}"
        ),
    }


def one_decision_cache() -> DecisionCache:
    item = candidate("one", PID_ONE, source_name="source name")
    return update_decision_cache(
        DecisionCache.empty(ADAPTER),
        plan(item),
        {PID_ONE: Disposition.ACCEPT},
        **review_details(),
    )


class DecisionCacheSerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "curation-decisions.yaml"

    def write_mapping(self, value: object) -> None:
        self.path.write_bytes(canonical_yaml_bytes(value))

    def assert_invalid(
        self,
        value: object,
        message: str,
    ) -> None:
        self.write_mapping(value)
        with self.assertRaisesRegex(ConfigurationError, message):
            load_decision_cache(self.path, adapter=ADAPTER)

    def test_missing_file_is_an_empty_valid_cache(self) -> None:
        cache = load_decision_cache(self.path, adapter=ADAPTER)

        self.assertEqual(cache, DecisionCache.empty(ADAPTER))
        self.assertEqual(
            serialize_decision_cache(cache).decode(),
            """adapter: example-adapter
decisions: {}
format: orinoco-lite-curation-decisions-v1
reviews: {}
""",
        )

    def test_exact_canonical_yaml_round_trip(self) -> None:
        cache = one_decision_cache()
        expected = """adapter: example-adapter
decisions:
  xyzrins:records/one:
    claim_sha256: sha256:b7902ea71b31c059060b0d69120194a808d6f73b72e5203ca78f5b2c98818f5b
    disposition: accept
    review: github-comment:123456
    source_record_id: one
format: orinoco-lite-curation-decisions-v1
reviews:
  github-comment:123456:
    review_url: https://github.com/con/site/pull/42#issuecomment-123456
    reviewed_at: '2026-08-20T18:42:00Z'
    reviewer: https://github.com/Reviewer-Name
    source_coordinate:
      revision: source-42
"""

        serialized = serialize_decision_cache(cache)
        self.assertEqual(serialized.decode(), expected)
        self.path.write_bytes(serialized)
        self.assertEqual(load_decision_cache(self.path, adapter=ADAPTER), cache)

    def test_noncanonical_yaml_is_rejected_even_when_values_are_valid(self) -> None:
        self.path.write_bytes(serialize_decision_cache(one_decision_cache()) + b"\n")

        with self.assertRaisesRegex(ConfigurationError, "exact canonical YAML"):
            load_decision_cache(self.path, adapter=ADAPTER)

    def test_schema_requires_exact_top_review_and_decision_fields(self) -> None:
        valid = one_decision_cache().to_mapping()
        cases: list[tuple[dict[str, object], str]] = []

        extra_top = deepcopy(valid)
        extra_top["history"] = []
        cases.append((extra_top, "unexpected history"))

        missing_top = deepcopy(valid)
        del missing_top["format"]
        cases.append((missing_top, "missing format"))

        extra_review = deepcopy(valid)
        extra_review["reviews"]["github-comment:123456"]["login"] = "Reviewer-Name"
        cases.append((extra_review, "unexpected login"))

        extra_decision = deepcopy(valid)
        extra_decision["decisions"][PID_ONE]["baseline"] = {}
        cases.append((extra_decision, "unexpected baseline"))

        for value, message in cases:
            with self.subTest(message=message):
                self.assert_invalid(value, message)

    def test_format_adapter_digest_and_disposition_are_strict(self) -> None:
        valid = one_decision_cache().to_mapping()
        cases: list[tuple[dict[str, object], str]] = []

        wrong_format = deepcopy(valid)
        wrong_format["format"] = "orinoco-lite-curation-decisions-v2"
        cases.append((wrong_format, "format must be"))

        wrong_adapter = deepcopy(valid)
        wrong_adapter["adapter"] = "another-adapter"
        cases.append((wrong_adapter, "adapter does not match"))

        uppercase_digest = deepcopy(valid)
        uppercase_digest["decisions"][PID_ONE]["claim_sha256"] = "sha256:" + "A" * 64
        cases.append((uppercase_digest, "lowercase sha256"))

        unknown_disposition = deepcopy(valid)
        unknown_disposition["decisions"][PID_ONE]["disposition"] = "ignore"
        cases.append((unknown_disposition, "accept, reject, or defer"))

        for value, message in cases:
            with self.subTest(message=message):
                self.assert_invalid(value, message)

    def test_pid_and_source_identities_are_unique(self) -> None:
        valid = one_decision_cache().to_mapping()
        duplicate_source = deepcopy(valid)
        duplicate_source["decisions"][PID_TWO] = {
            **duplicate_source["decisions"][PID_ONE],
            "claim_sha256": "sha256:" + "a" * 64,
        }
        self.assert_invalid(duplicate_source, "repeats a source record identity")

        serialized = serialize_decision_cache(one_decision_cache()).decode()
        duplicate_pid = serialized.replace(
            "format: orinoco-lite-curation-decisions-v1",
            """  xyzrins:records/one:
    claim_sha256: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    disposition: accept
    review: github-comment:123456
    source_record_id: one
format: orinoco-lite-curation-decisions-v1""",
        )
        self.path.write_text(duplicate_pid, encoding="utf-8")
        with self.assertRaisesRegex(ConfigurationError, "exact canonical YAML"):
            load_decision_cache(self.path, adapter=ADAPTER)

    def test_every_review_is_extant_and_referenced(self) -> None:
        valid = one_decision_cache().to_mapping()

        missing = deepcopy(valid)
        missing["decisions"][PID_ONE]["review"] = "github-comment:999"
        self.assert_invalid(missing, "references missing reviews")

        unreferenced = deepcopy(valid)
        unreferenced["reviews"]["github-comment:999"] = {
            "source_coordinate": {"revision": "source-99"},
            "reviewer": "https://github.com/Another-Reviewer",
            "reviewed_at": "2026-08-20T19:00:00Z",
            "review_url": "https://github.com/con/site/pull/42#issuecomment-999",
        }
        self.assert_invalid(unreferenced, "retains unreferenced reviews")


class ReviewProvenanceTests(unittest.TestCase):
    def test_reference_and_url_comment_ids_must_match(self) -> None:
        review = Review(
            source_coordinate=COORDINATE,
            reviewer="https://github.com/Reviewer-Name",
            reviewed_at="2026-08-20T18:42:00Z",
            review_url="https://github.com/con/site/pull/42#issuecomment-123456",
        )
        decision = Decision(
            source_record_id="one",
            claim_sha256="sha256:" + "a" * 64,
            disposition="accept",
            review="github-comment:999",
        )

        with self.assertRaisesRegex(ConfigurationError, "does not match"):
            DecisionCache(
                adapter=ADAPTER,
                reviews={"github-comment:999": review},
                decisions={PID_ONE: decision},
            )

        for reference in (
            "github-comment:0",
            "github-comment:0123",
            "github-comment:-1",
            "comment:123",
        ):
            with self.subTest(reference=reference), self.assertRaisesRegex(
                ConfigurationError, "positive decimal id"
            ):
                Decision(
                    source_record_id="one",
                    claim_sha256="sha256:" + "a" * 64,
                    disposition="accept",
                    review=reference,
                )

    def test_reviewer_is_the_exact_event_profile_url(self) -> None:
        valid = Review(
            source_coordinate=COORDINATE,
            reviewer="https://github.com/Mixed-Case.Login",
            reviewed_at="2026-08-20T18:42:00Z",
            review_url="https://github.com/con/site/pull/42#issuecomment-123456",
        )
        self.assertEqual(valid.reviewer, "https://github.com/Mixed-Case.Login")

        for reviewer in (
            "Reviewer-Name",
            "https://github.com/Reviewer-Name/",
            "https://github.com/owner/Reviewer-Name",
            "https://example.com/Reviewer-Name",
            "https://github.com/%52eviewer",
        ):
            with self.subTest(reviewer=reviewer), self.assertRaises(ConfigurationError):
                Review(
                    source_coordinate=COORDINATE,
                    reviewer=reviewer,
                    reviewed_at="2026-08-20T18:42:00Z",
                    review_url=(
                        "https://github.com/con/site/pull/42#issuecomment-123456"
                    ),
                )

    def test_review_url_is_exact_public_github_pull_comment_url(self) -> None:
        invalid = (
            "http://github.com/con/site/pull/42#issuecomment-123456",
            "https://enterprise.example/con/site/pull/42#issuecomment-123456",
            "https://github.com/con/site/issues/42#issuecomment-123456",
            "https://github.com/con/site/pull/0#issuecomment-123456",
            "https://github.com/con/site/pull/42/#issuecomment-123456",
            "https://github.com/con/site/pull/42#issuecomment-0123456",
            "https://github.com/con/site/pull/42#issuecomment-123456&x=1",
        )
        for review_url in invalid:
            with self.subTest(review_url=review_url), self.assertRaisesRegex(
                ConfigurationError, "exact public GitHub"
            ):
                Review(
                    source_coordinate=COORDINATE,
                    reviewer="https://github.com/Reviewer-Name",
                    reviewed_at="2026-08-20T18:42:00Z",
                    review_url=review_url,
                )

    def test_review_time_is_a_real_canonical_utc_second(self) -> None:
        invalid = (
            "2026-08-20T18:42:00+00:00",
            "2026-08-20T18:42:00.000Z",
            "2026-8-20T18:42:00Z",
            "2026-02-30T18:42:00Z",
        )
        for reviewed_at in invalid:
            with self.subTest(reviewed_at=reviewed_at), self.assertRaisesRegex(
                ConfigurationError, "Review time"
            ):
                Review(
                    source_coordinate=COORDINATE,
                    reviewer="https://github.com/Reviewer-Name",
                    reviewed_at=reviewed_at,
                    review_url=(
                        "https://github.com/con/site/pull/42#issuecomment-123456"
                    ),
                )

    def test_source_coordinate_is_nonempty_strict_json_and_detached(self) -> None:
        coordinate = {"revision": "source-42", "nested": {"page": 2}}
        review = Review(
            source_coordinate=coordinate,
            reviewer="https://github.com/Reviewer-Name",
            reviewed_at="2026-08-20T18:42:00Z",
            review_url="https://github.com/con/site/pull/42#issuecomment-123456",
        )
        coordinate["nested"]["page"] = 99
        exposed = review.source_coordinate
        exposed["nested"]["page"] = 100
        self.assertEqual(review.source_coordinate["nested"]["page"], 2)

        for invalid in ({}, {"bad": {1, 2}}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ConfigurationError, "source coordinate"
            ):
                Review(
                    source_coordinate=invalid,
                    reviewer="https://github.com/Reviewer-Name",
                    reviewed_at="2026-08-20T18:42:00Z",
                    review_url=(
                        "https://github.com/con/site/pull/42#issuecomment-123456"
                    ),
                )


class DecisionBehaviorTests(unittest.TestCase):
    def test_accept_and_reject_suppress_unchanged_human_corrected_claims(self) -> None:
        original = candidate("one", PID_ONE, source_name="source name")
        corrected = candidate(
            "one",
            PID_ONE,
            source_name="source name",
            baseline_name="human correction",
        )
        self.assertEqual(original.claim_sha256, corrected.claim_sha256)

        for disposition in (Disposition.ACCEPT, Disposition.REJECT):
            with self.subTest(disposition=disposition):
                cache = update_decision_cache(
                    DecisionCache.empty(ADAPTER),
                    plan(original),
                    {PID_ONE: disposition},
                    **review_details(),
                )
                rerun = plan(corrected)
                self.assertTrue(cache.is_suppressed(corrected))
                self.assertEqual(cache.candidates_requiring_review(rerun), ())

    def test_defer_returns_and_material_change_reopens(self) -> None:
        original = candidate("one", PID_ONE, source_name="source name")
        deferred = update_decision_cache(
            DecisionCache.empty(ADAPTER),
            plan(original),
            {PID_ONE: Disposition.DEFER},
            **review_details(),
        )
        self.assertFalse(deferred.is_suppressed(original))
        self.assertEqual(
            deferred.candidates_requiring_review(plan(original)),
            (original,),
        )

        accepted = update_decision_cache(
            DecisionCache.empty(ADAPTER),
            plan(original),
            {PID_ONE: Disposition.ACCEPT},
            **review_details(),
        )
        changed = candidate(
            "one",
            PID_ONE,
            source_name="material source change",
            baseline_name="human correction",
        )
        self.assertNotEqual(original.claim_sha256, changed.claim_sha256)
        self.assertFalse(accepted.is_suppressed(changed))
        self.assertEqual(
            accepted.candidates_requiring_review(plan(changed)),
            (changed,),
        )

    def test_suppression_requires_both_pid_and_source_identity(self) -> None:
        original = candidate("one", PID_ONE, source_name="source name")
        cache = update_decision_cache(
            DecisionCache.empty(ADAPTER),
            plan(original),
            {PID_ONE: Disposition.ACCEPT},
            **review_details(),
        )
        different_source = candidate(
            "different-source",
            PID_ONE,
            source_name="source name",
        )
        self.assertFalse(cache.is_suppressed(different_source))

    def test_update_requires_exact_coordinate_and_complete_candidates(self) -> None:
        first = candidate("one", PID_ONE, source_name="one")
        second = candidate("two", PID_TWO, source_name="two")
        current_plan = plan(first, second)

        with self.assertRaisesRegex(ConfigurationError, "source coordinate"):
            update_decision_cache(
                DecisionCache.empty(ADAPTER),
                current_plan,
                {PID_ONE: "accept", PID_TWO: "reject"},
                **review_details(coordinate={"revision": "source-43"}),
            )
        for dispositions in (
            {PID_ONE: "accept"},
            {PID_ONE: "accept", PID_TWO: "reject", "unknown": "defer"},
        ):
            with self.subTest(dispositions=dispositions), self.assertRaisesRegex(
                ConfigurationError, "complete candidate set"
            ):
                update_decision_cache(
                    DecisionCache.empty(ADAPTER),
                    current_plan,
                    dispositions,
                    **review_details(),
                )

    def test_proposal_plan_is_filtered_before_complete_update(self) -> None:
        unchanged = candidate("one", PID_ONE, source_name="source name")
        cache = update_decision_cache(
            DecisionCache.empty(ADAPTER),
            plan(unchanged),
            {PID_ONE: "accept"},
            **review_details(),
        )
        new = candidate("two", PID_TWO, source_name="new source claim")
        raw = plan(unchanged, new, coordinate={"revision": "source-43"})

        active = cache.candidates_requiring_review(raw)
        self.assertEqual(active, (new,))
        proposal = plan(*active, coordinate={"revision": "source-43"})
        cache = update_decision_cache(
            cache,
            proposal,
            {PID_TWO: "reject"},
            **review_details("200", coordinate={"revision": "source-43"}),
        )

        self.assertEqual(cache.decisions[PID_ONE].review, "github-comment:123456")
        self.assertEqual(cache.decisions[PID_TWO].review, "github-comment:200")

    def test_update_replaces_current_decisions_and_prunes_reviews(self) -> None:
        first = candidate("one", PID_ONE, source_name="one")
        second = candidate("two", PID_TWO, source_name="two")
        cache = update_decision_cache(
            DecisionCache.empty(ADAPTER),
            plan(first, second),
            {PID_ONE: "accept", PID_TWO: "reject"},
            **review_details("100"),
        )
        self.assertEqual(set(cache.reviews), {"github-comment:100"})

        changed_first = candidate(
            "one", PID_ONE, source_name="one changed", baseline_name="one"
        )
        cache = update_decision_cache(
            cache,
            plan(changed_first, coordinate={"revision": "source-43"}),
            {PID_ONE: "defer"},
            **review_details("200", coordinate={"revision": "source-43"}),
        )
        self.assertEqual(
            set(cache.reviews),
            {"github-comment:100", "github-comment:200"},
        )
        self.assertEqual(cache.decisions[PID_ONE].review, "github-comment:200")
        self.assertEqual(cache.decisions[PID_TWO].review, "github-comment:100")

        changed_second = candidate(
            "two", PID_TWO, source_name="two changed", baseline_name="two"
        )
        cache = update_decision_cache(
            cache,
            plan(changed_second, coordinate={"revision": "source-44"}),
            {PID_TWO: "accept"},
            **review_details("300", coordinate={"revision": "source-44"}),
        )
        self.assertEqual(
            set(cache.reviews),
            {"github-comment:200", "github-comment:300"},
        )
        self.assertEqual(cache.decisions[PID_TWO].review, "github-comment:300")

    def test_re_review_replaces_a_remapped_source_identity(self) -> None:
        cache = one_decision_cache()
        remapped = candidate(
            "one",
            PID_TWO,
            source_name="source name",
            baseline_name="different canonical record",
        )

        cache = update_decision_cache(
            cache,
            plan(remapped, coordinate={"revision": "source-43"}),
            {PID_TWO: "defer"},
            **review_details("200", coordinate={"revision": "source-43"}),
        )

        self.assertNotIn(PID_ONE, cache.decisions)
        self.assertEqual(cache.decisions[PID_TWO].source_record_id, "one")
        self.assertEqual(cache.decisions[PID_TWO].review, "github-comment:200")
        self.assertEqual(set(cache.reviews), {"github-comment:200"})

    def test_reusing_a_comment_cannot_change_authenticated_review_details(self) -> None:
        item = candidate("one", PID_ONE, source_name="source name")
        cache = one_decision_cache()

        with self.assertRaisesRegex(ConfigurationError, "different authenticated"):
            update_decision_cache(
                cache,
                plan(item),
                {PID_ONE: "accept"},
                **{
                    **review_details(),
                    "reviewer": "https://github.com/Another-Reviewer",
                },
            )

    def test_adapter_mismatch_fails_closed(self) -> None:
        item = candidate("one", PID_ONE, source_name="source name")
        other = CandidatePlan(
            adapter="another-adapter",
            adapter_version="1.0.0",
            adapter_agent_pid=AGENT_PID,
            source_namespace=NAMESPACE,
            source_coordinate=COORDINATE,
            metadata_base=BASE,
            candidates=(item,),
        )

        with self.assertRaisesRegex(ConfigurationError, "adapter does not match"):
            DecisionCache.empty(ADAPTER).candidates_requiring_review(other)


if __name__ == "__main__":
    unittest.main()
