from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
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


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


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
