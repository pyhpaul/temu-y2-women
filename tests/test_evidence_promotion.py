from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import unittest


_PROMOTION_FIXTURE_DIR = Path("tests/fixtures/promotion/dress")


class EvidencePromotionPrepareTest(unittest.TestCase):
    def test_prepare_dress_promotion_review_matches_expected_fixtures(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review

        for scenario in ("create", "update"):
            with self.subTest(scenario=scenario):
                scenario_dir = _PROMOTION_FIXTURE_DIR / scenario
                result = prepare_dress_promotion_review(
                    draft_elements_path=scenario_dir / "draft_elements.json",
                    draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                    active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                    active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                )

                self.assertEqual(
                    result,
                    _read_json(scenario_dir / "expected_review_template.json"),
                )

    def test_prepare_dress_promotion_review_rejects_invalid_staged_inputs(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review

        with TemporaryDirectory() as temp_dir:
            base_dir = _PROMOTION_FIXTURE_DIR / "create"
            invalid_elements = _read_json(base_dir / "draft_elements.json")
            invalid_elements["elements"][0]["price_bands"] = "mid"
            invalid_elements_path = Path(temp_dir) / "invalid-elements.json"
            _write_json(invalid_elements_path, invalid_elements)

            invalid_strategy = _read_json(base_dir / "draft_strategy_hints.json")
            invalid_strategy["strategy_hints"][0]["priority_signal"] = "high"
            invalid_strategy_path = Path(temp_dir) / "invalid-strategy.json"
            _write_json(invalid_strategy_path, invalid_strategy)

            for elements_path, strategies_path, field in (
                (invalid_elements_path, base_dir / "draft_strategy_hints.json", "price_bands"),
                (base_dir / "draft_elements.json", invalid_strategy_path, "priority_signal"),
            ):
                with self.subTest(field=field):
                    result = prepare_dress_promotion_review(
                        draft_elements_path=elements_path,
                        draft_strategy_hints_path=strategies_path,
                        active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                        active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                    )

                    self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_INPUT")
                    self.assertEqual(result["error"]["details"]["field"], field)

    def test_prepare_dress_promotion_review_rejects_malformed_active_evidence_json(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review

        with TemporaryDirectory() as temp_dir:
            broken_elements_path = Path(temp_dir) / "broken-elements.json"
            broken_elements_path.write_text("{bad", encoding="utf-8")
            result = prepare_dress_promotion_review(
                draft_elements_path=_PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json",
                draft_strategy_hints_path=_PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json",
                active_elements_path=broken_elements_path,
                active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
            )

        self.assertEqual(result["error"]["code"], "INVALID_EVIDENCE_STORE")

    def test_prepare_dress_promotion_review_surfaces_merge_rationale_and_canonical_identity(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review

        result = prepare_dress_promotion_review(
            draft_elements_path=_PROMOTION_FIXTURE_DIR / "update" / "draft_elements.json",
            draft_strategy_hints_path=_PROMOTION_FIXTURE_DIR / "update" / "draft_strategy_hints.json",
            active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
            active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
        )

        element = result["elements"][0]
        strategy = result["strategy_hints"][0]
        self.assertIn("canonical_identity", element)
        self.assertIn("merge_rationale", element)
        self.assertIn("canonical_identity", strategy)
        self.assertIn("merge_rationale", strategy)

    def test_prepare_dress_promotion_review_preserves_active_element_strength_on_update(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review

        result = prepare_dress_promotion_review(
            draft_elements_path=_PROMOTION_FIXTURE_DIR / "update" / "draft_elements.json",
            draft_strategy_hints_path=_PROMOTION_FIXTURE_DIR / "update" / "draft_strategy_hints.json",
            active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
            active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
        )

        proposed = result["elements"][0]["proposed_element"]
        self.assertEqual(proposed["base_score"], 0.8)
        self.assertEqual(proposed["tags"], ["breathable", "lightweight", "summer", "vacation"])
        self.assertEqual(proposed["price_bands"], ["mid"])
        self.assertEqual(proposed["occasion_tags"], ["casual", "resort", "vacation"])
        self.assertEqual(proposed["season_tags"], ["spring", "summer"])
        self.assertEqual(proposed["risk_flags"], [])

    def test_prepare_dress_promotion_review_preserves_active_strategy_window_and_boost_on_update(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review

        result = prepare_dress_promotion_review(
            draft_elements_path=_PROMOTION_FIXTURE_DIR / "update" / "draft_elements.json",
            draft_strategy_hints_path=_PROMOTION_FIXTURE_DIR / "update" / "draft_strategy_hints.json",
            active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
            active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
        )

        proposed = result["strategy_hints"][0]["proposed_strategy_template"]
        self.assertEqual(proposed["priority"], 8)
        self.assertEqual(proposed["date_window"], {"start": "05-15", "end": "08-31"})
        self.assertEqual(proposed["score_boost"], 0.09)
        self.assertEqual(proposed["score_cap"], 0.15)
        self.assertEqual(proposed["occasion_tags"], ["resort", "vacation"])
        self.assertEqual(proposed["suppress_tags"], ["bodycon", "holiday"])
        self.assertEqual(
            proposed["boost_tags"],
            ["airy", "breathable", "floral", "summer"],
        )
        self.assertEqual(
            proposed["prompt_hints"],
            [
                "breathable summer dress assortment",
                "easy feminine vacation styling",
                "Aggregated from 3 signals for refreshed summer vacation dress demand.",
            ],
        )
        self.assertEqual(
            proposed["reason_template"],
            "summer vacation timing favors breathable feminine dress cues with broad seasonal reuse",
        )

    def test_prepare_dress_promotion_review_surfaces_structured_review_context(self) -> None:
        from temu_y2_women.evidence_promotion import prepare_dress_promotion_review
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")
            refresh_result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-29T00:00:00Z",
                fetcher=_mixed_registry_fetcher(),
                card_image_observer=_fake_card_observer_with_new_value,
            )
            run_dir = temp_root / refresh_result["run_id"]
            result = prepare_dress_promotion_review(
                draft_elements_path=run_dir / "draft_elements.json",
                draft_strategy_hints_path=run_dir / "draft_strategy_hints.json",
                active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
            )

        gingham = next(item for item in result["elements"] if item["draft_id"] == "draft-pattern-gingham-check")
        self.assertEqual(gingham["review_context"]["matched_channels"], ["structured_candidate"])
        self.assertEqual(len(gingham["review_context"]["structured_matches"]), 1)
        match = gingham["review_context"]["structured_matches"][0]
        self.assertEqual(match["signal_id"], "whowhatwear-best-summer-dresses-2025-pattern-gingham-check-001")
        self.assertEqual(match["slot"], "pattern")
        self.assertEqual(match["value"], "gingham check")
        self.assertEqual(match["candidate_source"], "roundup_card_image_aggregation")
        self.assertEqual(
            match["supporting_card_ids"],
            [
                "whowhatwear-best-summer-dresses-2025-card-001",
                "whowhatwear-best-summer-dresses-2025-card-002",
            ],
        )
        self.assertEqual(match["supporting_card_count"], 2)
        self.assertEqual(match["aggregation_threshold"], 2)
        self.assertEqual(match["observation_model"], "fake-card-observer-with-new-value")
        self.assertIn("pattern=gingham check", match["evidence_summary"])


class EvidencePromotionValidationTest(unittest.TestCase):
    def test_validate_reviewed_dress_promotion_accepts_valid_reviewed_fixtures(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        for scenario in ("create", "update"):
            with self.subTest(scenario=scenario):
                scenario_dir = _PROMOTION_FIXTURE_DIR / scenario
                result = validate_reviewed_dress_promotion(
                    reviewed_path=scenario_dir / "reviewed_decisions.json",
                    draft_elements_path=scenario_dir / "draft_elements.json",
                    draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                    active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                    active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                )

                self.assertEqual(result, _read_json(scenario_dir / "reviewed_decisions.json"))

    def test_validate_reviewed_dress_promotion_rejects_invalid_reviewed_inputs(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "create"
            invalid_decision_path = Path(temp_dir) / "invalid-decision.json"
            invalid_strategy_path = Path(temp_dir) / "invalid-strategy.json"

            invalid_decision = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_decision["elements"][0]["decision"] = "pending"
            _write_json(invalid_decision_path, invalid_decision)

            invalid_strategy = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_strategy["strategy_hints"][0]["proposed_strategy_template"]["slot_preferences"]["detail"] = [
                "not-on-active-evidence"
            ]
            _write_json(invalid_strategy_path, invalid_strategy)

            for reviewed_path, field in (
                (invalid_decision_path, "decision"),
                (invalid_strategy_path, "slot_preferences"),
            ):
                with self.subTest(path=reviewed_path.name):
                    result = validate_reviewed_dress_promotion(
                        reviewed_path=reviewed_path,
                        draft_elements_path=scenario_dir / "draft_elements.json",
                        draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                        active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                        active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                    )

                    self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
                    self.assertEqual(result["error"]["details"]["field"], field)

    def test_validate_reviewed_dress_promotion_rejects_malformed_curated_overrides(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "create"
            invalid_price_bands = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_price_bands["elements"][0]["proposed_element"]["price_bands"] = "mid"
            invalid_price_bands_path = Path(temp_dir) / "invalid-price-bands.json"
            _write_json(invalid_price_bands_path, invalid_price_bands)

            invalid_priority = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_priority["strategy_hints"][0]["proposed_strategy_template"]["priority"] = "high"
            invalid_priority_path = Path(temp_dir) / "invalid-priority.json"
            _write_json(invalid_priority_path, invalid_priority)

            invalid_score_boost = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_score_boost["strategy_hints"][0]["proposed_strategy_template"]["score_boost"] = "bad"
            invalid_score_boost_path = Path(temp_dir) / "invalid-score-boost.json"
            _write_json(invalid_score_boost_path, invalid_score_boost)

            duplicate_strategy_id = _read_json(scenario_dir / "reviewed_decisions.json")
            duplicate_strategy_id["strategy_hints"][0]["proposed_strategy_template"]["strategy_id"] = (
                "dress-us-summer-vacation"
            )
            duplicate_strategy_id_path = Path(temp_dir) / "duplicate-strategy-id.json"
            _write_json(duplicate_strategy_id_path, duplicate_strategy_id)

            for reviewed_path, field in (
                (invalid_price_bands_path, "price_bands"),
                (invalid_priority_path, "priority"),
                (invalid_score_boost_path, "score_boost"),
                (duplicate_strategy_id_path, "strategy_id"),
            ):
                with self.subTest(field=field):
                    result = validate_reviewed_dress_promotion(
                        reviewed_path=reviewed_path,
                        draft_elements_path=scenario_dir / "draft_elements.json",
                        draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                        active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                        active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                    )

                    self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
                    self.assertEqual(result["error"]["details"]["field"], field)

    def test_validate_reviewed_dress_promotion_rejects_duplicate_review_records(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            draft_elements = _combined_payload("draft_elements.json", "elements")
            draft_strategy_hints = _combined_payload("draft_strategy_hints.json", "strategy_hints")
            reviewed = _combined_reviewed_payload()
            reviewed["elements"] = [reviewed["elements"][0], dict(reviewed["elements"][0])]
            reviewed["strategy_hints"] = [reviewed["strategy_hints"][0], dict(reviewed["strategy_hints"][1])]

            draft_elements_path = temp_root / "draft_elements.json"
            draft_strategy_hints_path = temp_root / "draft_strategy_hints.json"
            reviewed_path = temp_root / "reviewed.json"
            _write_json(draft_elements_path, draft_elements)
            _write_json(draft_strategy_hints_path, draft_strategy_hints)
            _write_json(reviewed_path, reviewed)

            result = validate_reviewed_dress_promotion(
                reviewed_path=reviewed_path,
                draft_elements_path=draft_elements_path,
                draft_strategy_hints_path=draft_strategy_hints_path,
                active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
            )

            self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
            self.assertEqual(result["error"]["details"]["field"], "draft_id")

    def test_validate_reviewed_dress_promotion_rejects_update_id_tampering(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "update"
            invalid_element = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_element["elements"][0]["proposed_element"]["element_id"] = "renamed-element-id"
            invalid_element_path = Path(temp_dir) / "invalid-element-id.json"
            _write_json(invalid_element_path, invalid_element)

            invalid_strategy = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_strategy["strategy_hints"][0]["proposed_strategy_template"]["strategy_id"] = "renamed-strategy-id"
            invalid_strategy_path = Path(temp_dir) / "invalid-strategy-id.json"
            _write_json(invalid_strategy_path, invalid_strategy)

            for reviewed_path, field in (
                (invalid_element_path, "element_id"),
                (invalid_strategy_path, "strategy_id"),
            ):
                with self.subTest(field=field):
                    result = validate_reviewed_dress_promotion(
                        reviewed_path=reviewed_path,
                        draft_elements_path=scenario_dir / "draft_elements.json",
                        draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                        active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                        active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                    )

                    self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
                    self.assertEqual(result["error"]["details"]["field"], field)

    def test_validate_reviewed_dress_promotion_rejects_invalid_reject_payload_types(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "create"
            invalid_element = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_element["elements"][0]["decision"] = "reject"
            invalid_element["elements"][0]["proposed_element"] = 123
            invalid_element["strategy_hints"][0]["decision"] = "reject"
            invalid_element["strategy_hints"][0]["proposed_strategy_template"] = None
            invalid_element_path = Path(temp_dir) / "invalid-reject-element.json"
            _write_json(invalid_element_path, invalid_element)

            invalid_strategy = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_strategy["elements"][0]["decision"] = "reject"
            invalid_strategy["elements"][0]["proposed_element"] = None
            invalid_strategy["strategy_hints"][0]["decision"] = "reject"
            invalid_strategy["strategy_hints"][0]["proposed_strategy_template"] = ["x"]
            invalid_strategy_path = Path(temp_dir) / "invalid-reject-strategy.json"
            _write_json(invalid_strategy_path, invalid_strategy)

            for reviewed_path, field in (
                (invalid_element_path, "proposed_element"),
                (invalid_strategy_path, "proposed_strategy_template"),
            ):
                with self.subTest(field=field):
                    result = validate_reviewed_dress_promotion(
                        reviewed_path=reviewed_path,
                        draft_elements_path=scenario_dir / "draft_elements.json",
                        draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                        active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                        active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                    )

                    self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
                    self.assertEqual(result["error"]["details"]["field"], field)

    def test_validate_reviewed_dress_promotion_rejects_merge_semantic_tampering(self) -> None:
        from temu_y2_women.evidence_promotion import validate_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "update"
            invalid_identity = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_identity["elements"][0]["canonical_identity"] = {
                "slot": "fabric",
                "value": "linen blend",
            }
            invalid_identity_path = Path(temp_dir) / "invalid-identity.json"
            _write_json(invalid_identity_path, invalid_identity)

            invalid_rationale = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_rationale["strategy_hints"][0]["merge_rationale"] = {
                "rule": "resolved-strategy-id",
                "resolved_strategy_id": "dress-us-summer-vacation-shadow",
                "matched_active_strategy_id": "dress-us-summer-vacation",
            }
            invalid_rationale_path = Path(temp_dir) / "invalid-rationale.json"
            _write_json(invalid_rationale_path, invalid_rationale)

            for reviewed_path, field in (
                (invalid_identity_path, "canonical_identity"),
                (invalid_rationale_path, "merge_rationale"),
            ):
                with self.subTest(field=field):
                    result = validate_reviewed_dress_promotion(
                        reviewed_path=reviewed_path,
                        draft_elements_path=scenario_dir / "draft_elements.json",
                        draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                        active_elements_path=_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json",
                        active_strategies_path=_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json",
                    )

                    self.assertIn("error", result)
                    self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
                    self.assertEqual(result["error"]["details"]["field"], field)


class EvidencePromotionApplyTest(unittest.TestCase):
    def test_apply_reviewed_dress_promotion_writes_expected_outputs(self) -> None:
        from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion

        for scenario in ("create", "update"):
            with self.subTest(scenario=scenario):
                with TemporaryDirectory() as temp_dir:
                    scenario_dir = _PROMOTION_FIXTURE_DIR / scenario
                    temp_root = Path(temp_dir)
                    elements_path, strategies_path = _seed_active_evidence(temp_root)
                    report_path = temp_root / "promotion_report.json"

                    result = apply_reviewed_dress_promotion(
                        reviewed_path=scenario_dir / "reviewed_decisions.json",
                        draft_elements_path=scenario_dir / "draft_elements.json",
                        draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                        active_elements_path=elements_path,
                        active_strategies_path=strategies_path,
                        report_path=report_path,
                    )

                    self.assertEqual(result, _read_json(scenario_dir / "expected_promotion_report.json"))
                    self.assertEqual(_read_json(elements_path), _read_json(scenario_dir / "expected_elements_after_apply.json"))
                    self.assertEqual(
                        _read_json(strategies_path),
                        _read_json(scenario_dir / "expected_strategy_templates_after_apply.json"),
                    )
                    self.assertEqual(_read_json(report_path), _read_json(scenario_dir / "expected_promotion_report.json"))

    def test_apply_reviewed_dress_promotion_fails_before_mutation(self) -> None:
        from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "create"
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            report_path = temp_root / "promotion_report.json"
            before_elements = elements_path.read_text(encoding="utf-8")
            before_strategies = strategies_path.read_text(encoding="utf-8")

            invalid_review = _read_json(scenario_dir / "reviewed_decisions.json")
            invalid_review["strategy_hints"][0]["proposed_strategy_template"]["slot_preferences"]["detail"] = ["missing"]
            invalid_review_path = temp_root / "invalid_review.json"
            _write_json(invalid_review_path, invalid_review)

            result = apply_reviewed_dress_promotion(
                reviewed_path=invalid_review_path,
                draft_elements_path=scenario_dir / "draft_elements.json",
                draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
                report_path=report_path,
            )

            self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
            self.assertEqual(elements_path.read_text(encoding="utf-8"), before_elements)
            self.assertEqual(strategies_path.read_text(encoding="utf-8"), before_strategies)
            self.assertFalse(report_path.exists())

    def test_apply_reviewed_dress_promotion_skips_rejected_records(self) -> None:
        from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "create"
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            report_path = temp_root / "promotion_report.json"
            reviewed = _read_json(scenario_dir / "reviewed_decisions.json")
            reviewed["elements"][0]["decision"] = "reject"
            reviewed["elements"][0]["proposed_element"] = None
            reviewed["strategy_hints"][0]["decision"] = "reject"
            reviewed["strategy_hints"][0]["proposed_strategy_template"] = None
            reviewed_path = temp_root / "rejected_review.json"
            _write_json(reviewed_path, reviewed)

            result = apply_reviewed_dress_promotion(
                reviewed_path=reviewed_path,
                draft_elements_path=scenario_dir / "draft_elements.json",
                draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
                report_path=report_path,
            )

            self.assertEqual(result["summary"]["elements"], {"accepted": 0, "rejected": 1, "created": 0, "updated": 0})
            self.assertEqual(result["summary"]["strategy_hints"], {"accepted": 0, "rejected": 1, "created": 0, "updated": 0})
            self.assertEqual(_read_json(elements_path), _read_json(_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json"))
            self.assertEqual(
                _read_json(strategies_path),
                _read_json(_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json"),
            )

    def test_apply_reviewed_dress_promotion_rejects_write_stage_partial_mutation(self) -> None:
        from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "create"
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            before_elements = elements_path.read_text(encoding="utf-8")
            before_strategies = strategies_path.read_text(encoding="utf-8")
            report_path = temp_root / "missing-dir" / "promotion_report.json"

            result = apply_reviewed_dress_promotion(
                reviewed_path=scenario_dir / "reviewed_decisions.json",
                draft_elements_path=scenario_dir / "draft_elements.json",
                draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
                report_path=report_path,
            )

            self.assertEqual(result["error"]["code"], "PROMOTION_WRITE_FAILED")
            self.assertEqual(elements_path.read_text(encoding="utf-8"), before_elements)
            self.assertEqual(strategies_path.read_text(encoding="utf-8"), before_strategies)
            self.assertFalse(report_path.exists())

    def test_apply_reviewed_dress_promotion_accepts_objective_slots(self) -> None:
        from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "objective_slots"
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            report_path = temp_root / "promotion_report.json"

            result = apply_reviewed_dress_promotion(
                reviewed_path=scenario_dir / "reviewed_decisions.json",
                draft_elements_path=scenario_dir / "draft_elements.json",
                draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
                report_path=report_path,
            )

            self.assertEqual(result, _read_json(scenario_dir / "expected_promotion_report.json"))
            self.assertEqual(_read_json(elements_path), _read_json(scenario_dir / "expected_elements_after_apply.json"))
            self.assertEqual(
                _read_json(strategies_path),
                _read_json(scenario_dir / "expected_strategy_templates_after_apply.json"),
            )
            self.assertEqual(result["summary"]["elements"]["accepted"], 2)
            self.assertEqual(result["summary"]["strategy_hints"]["accepted"], 1)

    def test_apply_reviewed_dress_promotion_accepts_default_update_review_without_degrading_active_strength(self) -> None:
        from temu_y2_women.evidence_promotion import (
            apply_reviewed_dress_promotion,
            prepare_dress_promotion_review,
        )

        with TemporaryDirectory() as temp_dir:
            scenario_dir = _PROMOTION_FIXTURE_DIR / "update"
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            report_path = temp_root / "promotion_report.json"
            reviewed = prepare_dress_promotion_review(
                draft_elements_path=scenario_dir / "draft_elements.json",
                draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )
            for record in reviewed["elements"]:
                record["decision"] = "accept"
            for record in reviewed["strategy_hints"]:
                record["decision"] = "accept"
            reviewed_path = temp_root / "prepared-review.json"
            _write_json(reviewed_path, reviewed)

            result = apply_reviewed_dress_promotion(
                reviewed_path=reviewed_path,
                draft_elements_path=scenario_dir / "draft_elements.json",
                draft_strategy_hints_path=scenario_dir / "draft_strategy_hints.json",
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
                report_path=report_path,
            )

            self.assertNotIn("error", result)
            applied_elements = _read_json(elements_path)["elements"]
            applied_strategies = _read_json(strategies_path)["strategy_templates"]
            cotton_poplin = next(item for item in applied_elements if item["element_id"] == "dress-fabric-cotton-poplin-001")
            summer_vacation = next(
                item for item in applied_strategies if item["strategy_id"] == "dress-us-summer-vacation"
            )
            self.assertEqual(cotton_poplin["base_score"], 0.8)
            self.assertEqual(cotton_poplin["occasion_tags"], ["casual", "resort", "vacation"])
            self.assertEqual(summer_vacation["priority"], 8)
            self.assertEqual(summer_vacation["date_window"], {"start": "05-15", "end": "08-31"})
            self.assertEqual(summer_vacation["boost_tags"], ["airy", "breathable", "floral", "summer"])
            self.assertEqual(summer_vacation["score_boost"], 0.09)
            self.assertEqual(summer_vacation["score_cap"], 0.15)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _mixed_source_registry() -> dict[str, object]:
    return {
        "schema_version": "public-source-registry-v1",
        "sources": [
            {
                "source_id": "whowhatwear-summer-2025-dress-trends",
                "source_type": "public_editorial_web",
                "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                "target_market": "US",
                "category": "dress",
                "fetch_mode": "html",
                "adapter_id": "whowhatwear_editorial_v1",
                "default_price_band": "mid",
                "pipeline_mode": "editorial_text",
                "priority": 100,
                "weight": 1.0,
                "enabled": True,
            },
            {
                "source_id": "whowhatwear-best-summer-dresses-2025",
                "source_type": "public_roundup_web",
                "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
                "target_market": "US",
                "category": "dress",
                "fetch_mode": "html",
                "adapter_id": "whowhatwear_roundup_v1",
                "default_price_band": "mid",
                "pipeline_mode": "roundup_image_cards",
                "card_limit": 12,
                "aggregation_threshold": 2,
                "observation_model": "gpt-4.1-mini",
                "priority": 70,
                "weight": 0.7,
                "enabled": True,
            },
        ],
    }


def _mixed_registry_fetcher() -> Callable[[str], str]:
    html_by_url = {
        "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends": (
            Path("tests/fixtures/public_sources/dress/whowhatwear-summer-2025-dress-trends.html")
        ).read_text(encoding="utf-8"),
        "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025": (
            Path("tests/fixtures/public_sources/dress/whowhatwear-best-summer-dresses-2025.html")
        ).read_text(encoding="utf-8"),
    }

    def fetcher(url: str) -> str:
        return html_by_url[url]

    return fetcher


def _fake_card_observer_with_new_value(card: dict[str, object]) -> dict[str, object]:
    if str(card["card_id"]).endswith(("001", "002")):
        return {
            "observed_slots": [
                {
                    "slot": "pattern",
                    "value": "gingham check",
                    "evidence_summary": "small two-tone checks repeat across the dress",
                },
            ],
            "abstained_slots": ["opacity_level"],
            "warnings": [],
        }
    return {
        "observed_slots": [
            {"slot": "waistline", "value": "drop waist", "evidence_summary": "seam sits below natural waist"},
        ],
        "abstained_slots": ["opacity_level"],
        "warnings": [],
    }


def _combined_payload(filename: str, field: str) -> dict[str, object]:
    create_payload = _read_json(_PROMOTION_FIXTURE_DIR / "create" / filename)
    update_payload = _read_json(_PROMOTION_FIXTURE_DIR / "update" / filename)
    return {
        "schema_version": create_payload["schema_version"],
        field: [*create_payload[field], *update_payload[field]],
    }


def _combined_reviewed_payload() -> dict[str, object]:
    create_reviewed = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json")
    update_reviewed = _read_json(_PROMOTION_FIXTURE_DIR / "update" / "reviewed_decisions.json")
    return {
        "schema_version": create_reviewed["schema_version"],
        "category": create_reviewed["category"],
        "elements": [*create_reviewed["elements"], *update_reviewed["elements"]],
        "strategy_hints": [*create_reviewed["strategy_hints"], *update_reviewed["strategy_hints"]],
    }


def _seed_active_evidence(temp_root: Path) -> tuple[Path, Path]:
    elements_path = temp_root / "elements.json"
    strategies_path = temp_root / "strategy_templates.json"
    elements_path.write_text(
        (_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    strategies_path.write_text(
        (_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return elements_path, strategies_path
