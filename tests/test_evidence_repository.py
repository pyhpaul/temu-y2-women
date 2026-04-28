from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class EvidenceRepositoryValidationTest(unittest.TestCase):
    @staticmethod
    def _write_taxonomy(path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "allowed_slots": [
                        "silhouette",
                        "fabric",
                        "neckline",
                        "sleeve",
                        "pattern",
                        "detail",
                    ],
                    "allowed_tags": [
                        "airy",
                        "bodycon",
                        "casual",
                        "dress",
                        "feminine",
                        "fit_sensitivity",
                        "floral",
                        "heavy",
                        "holiday",
                        "lightweight",
                        "summer",
                        "vacation",
                    ],
                    "allowed_occasions": ["casual", "party", "resort", "vacation"],
                    "allowed_seasons": ["spring", "summer"],
                    "allowed_risk_flags": ["fit_sensitivity"],
                    "summary": {"min_length": 20, "max_length": 140},
                    "base_score": {"min": 0.0, "max": 1.0},
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _base_element(**overrides: object) -> dict[str, object]:
        element: dict[str, object] = {
            "element_id": "dress-silhouette-a-line-001",
            "category": "dress",
            "slot": "silhouette",
            "value": "a-line",
            "tags": ["summer", "feminine"],
            "base_score": 0.82,
            "price_bands": ["mid"],
            "occasion_tags": ["casual"],
            "season_tags": ["summer"],
            "risk_flags": [],
            "evidence_summary": "Known silhouette fixture with valid taxonomy-backed authoring defaults.",
            "status": "active",
        }
        element.update(overrides)
        return element

    @staticmethod
    def _write_elements_store(path: Path, elements: list[dict[str, object]]) -> None:
        path.write_text(
            json.dumps({"schema_version": "mvp-v1", "elements": elements}),
            encoding="utf-8",
        )

    @staticmethod
    def _base_strategy(**overrides: object) -> dict[str, object]:
        strategy: dict[str, object] = {
            "strategy_id": "dress-us-baseline",
            "category": "dress",
            "target_market": "US",
            "priority": 1,
            "date_window": {"start": "01-01", "end": "12-31"},
            "occasion_tags": [],
            "boost_tags": ["summer"],
            "suppress_tags": [],
            "slot_preferences": {"silhouette": ["a-line"]},
            "score_boost": 0.03,
            "score_cap": 0.08,
            "prompt_hints": ["baseline"],
            "reason_template": "baseline",
            "status": "active",
        }
        strategy.update(overrides)
        return strategy

    @staticmethod
    def _write_strategy_store(path: Path, strategies: list[dict[str, object]]) -> None:
        path.write_text(
            json.dumps({"schema_version": "mvp-v1", "strategy_templates": strategies}),
            encoding="utf-8",
        )

    @staticmethod
    def _to_selected_strategy(strategy_record: dict[str, object], reason: str):
        from temu_y2_women.models import DateWindow, SelectedStrategy, StrategyTemplate

        return SelectedStrategy(
            strategy=StrategyTemplate(
                strategy_id=str(strategy_record["strategy_id"]),
                category=str(strategy_record["category"]),
                target_market=str(strategy_record["target_market"]),
                priority=int(strategy_record["priority"]),
                date_window=DateWindow(**strategy_record["date_window"]),
                occasion_tags=tuple(strategy_record["occasion_tags"]),
                boost_tags=tuple(strategy_record["boost_tags"]),
                suppress_tags=tuple(strategy_record["suppress_tags"]),
                slot_preferences={
                    key: tuple(values) for key, values in strategy_record["slot_preferences"].items()
                },
                score_boost=float(strategy_record["score_boost"]),
                score_cap=float(strategy_record["score_cap"]),
                prompt_hints=tuple(strategy_record["prompt_hints"]),
                reason_template=str(strategy_record["reason_template"]),
                status=str(strategy_record["status"]),
            ),
            reason=reason,
        )

    def test_reject_missing_elements_wrapper(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            path = temp_root / "elements.json"
            path.write_text(json.dumps({"schema_version": "mvp-v1"}), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_elements(path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "elements evidence store must contain an 'elements' array",
        )
        self.assertEqual(error_context.exception.details["path"], str(path))

    def test_reject_non_object_taxonomy_root(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_evidence_taxonomy

        with TemporaryDirectory() as temp_dir:
            taxonomy_path = Path(temp_dir) / "evidence_taxonomy.json"
            taxonomy_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_evidence_taxonomy(taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.message, "evidence taxonomy root must be an object")
        self.assertEqual(error_context.exception.details["path"], str(taxonomy_path))

    def test_reject_non_object_elements_root(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.message, "elements evidence store root must be an object")
        self.assertEqual(error_context.exception.details["path"], str(elements_path))

    def test_reject_missing_strategy_templates_wrapper(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_strategy_templates

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Known silhouette used to isolate strategy wrapper validation.",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            path = temp_root / "strategy_templates.json"
            path.write_text(json.dumps({"schema_version": "mvp-v1"}), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_strategy_templates(
                    path,
                    taxonomy_path=taxonomy_path,
                    elements_path=elements_path,
                )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "strategy evidence store must contain a 'strategy_templates' array",
        )
        self.assertEqual(error_context.exception.details["path"], str(path))

    def test_reject_non_object_strategy_templates_root(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_strategy_templates

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Known silhouette used to isolate strategy root validation.",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            strategies_path = temp_root / "strategy_templates.json"
            strategies_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_strategy_templates(
                    strategies_path,
                    taxonomy_path=taxonomy_path,
                    elements_path=elements_path,
                )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "strategy evidence store root must be an object",
        )
        self.assertEqual(error_context.exception.details["path"], str(strategies_path))

    def test_reject_invalid_nested_strategy_shape(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_strategy_templates

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            self._write_elements_store(
                elements_path,
                [
                    self._base_element(
                        evidence_summary="Known silhouette used to isolate nested strategy validation."
                    )
                ],
            )
            path = temp_root / "strategy_templates.json"
            self._write_strategy_store(
                path,
                [
                    self._base_strategy(
                        strategy_id="broken",
                        date_window="05-15..08-31",
                        boost_tags=[],
                        slot_preferences={},
                        score_boost=0.1,
                        score_cap=0.1,
                        prompt_hints=[],
                        reason_template="broken",
                    )
                ],
            )

            with self.assertRaises(GenerationError) as error_context:
                load_strategy_templates(
                    path,
                    taxonomy_path=taxonomy_path,
                    elements_path=elements_path,
                )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "strategy date_window must be an object",
        )
        self.assertEqual(error_context.exception.details["field"], "date_window")

    def test_reject_unknown_element_tag(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["unknown-tag"],
                                "base_score": 0.8,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Commercial summer silhouette with clear casual demand.",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "element field 'tags' contains unknown taxonomy values",
        )
        self.assertEqual(error_context.exception.details["field"], "tags")
        self.assertEqual(error_context.exception.details["values"], ["unknown-tag"])

    def test_accepts_inactive_invalid_element_record(self) -> None:
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Active element keeps the evidence store loadable for inactive validation.",
                                "status": "active",
                            },
                            {
                                "element_id": "draft-invalid-element",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "draft-shape",
                                "tags": ["unknown-tag"],
                                "base_score": 9.5,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "short",
                                "status": "inactive",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            elements = load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[1]["status"], "inactive")

    def test_reject_invalid_unknown_tag_fixture(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        fixture_path = Path("tests/fixtures/evidence/dress/invalid-unknown-tag-elements.json")
        taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")

        with self.assertRaises(GenerationError) as error_context:
            load_elements(fixture_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "element field 'tags' contains unknown taxonomy values",
        )
        self.assertEqual(error_context.exception.details["path"], str(fixture_path))
        self.assertEqual(error_context.exception.details["index"], 0)
        self.assertEqual(error_context.exception.details["field"], "tags")
        self.assertEqual(error_context.exception.details["values"], ["unknown-tag"])

    def test_reject_duplicate_active_slot_value(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Baseline commercial silhouette with clear summer appeal.",
                                "status": "active",
                            },
                            {
                                "element_id": "dress-silhouette-a-line-002",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "casual"],
                                "base_score": 0.79,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Duplicate active value used to prove conflict detection.",
                                "status": "active",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "active element duplicates an existing slot/value record",
        )
        self.assertEqual(error_context.exception.details["slot"], "silhouette")
        self.assertEqual(error_context.exception.details["value"], "a-line")

    def test_reject_invalid_duplicate_elements_fixture(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        fixture_path = Path("tests/fixtures/evidence/dress/invalid-duplicate-elements.json")
        taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")

        with self.assertRaises(GenerationError) as error_context:
            load_elements(fixture_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "active element duplicates an existing slot/value record",
        )
        self.assertEqual(error_context.exception.details["path"], str(fixture_path))
        self.assertEqual(error_context.exception.details["index"], 1)
        self.assertEqual(error_context.exception.details["slot"], "silhouette")
        self.assertEqual(error_context.exception.details["value"], "a-line")

    def test_reject_canonical_duplicate_active_slot_value(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Baseline silhouette used to validate canonical duplicate detection.",
                                "status": "active",
                            },
                            {
                                "element_id": "dress-silhouette-a-line-002",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "  A-LINE  ",
                                "tags": ["summer", "casual"],
                                "base_score": 0.79,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Whitespace and case variants should still count as duplicates.",
                                "status": "active",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "active element duplicates an existing slot/value record",
        )
        self.assertEqual(error_context.exception.details["slot"], "silhouette")
        self.assertEqual(error_context.exception.details["value"], "  A-LINE  ")

    def test_reject_duplicate_active_element_id(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Known silhouette used to validate duplicate element identifiers.",
                                "status": "active",
                            },
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "fabric",
                                "value": "cotton poplin",
                                "tags": ["summer", "lightweight"],
                                "base_score": 0.84,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Duplicate active identifier should fail even when slot and value differ.",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "active element duplicates an existing element_id record",
        )
        self.assertEqual(error_context.exception.details["element_id"], "dress-silhouette-a-line-001")

    def test_reject_invalid_base_score(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 1.5,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "Out of range score should fail authoring-quality validation.",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "element base_score is outside the allowed taxonomy range",
        )
        self.assertEqual(error_context.exception.details["field"], "base_score")
        self.assertEqual(error_context.exception.details["value"], 1.5)

    def test_reject_invalid_evidence_summary(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-silhouette-a-line-001",
                                "category": "dress",
                                "slot": "silhouette",
                                "value": "a-line",
                                "tags": ["summer", "feminine"],
                                "base_score": 0.82,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["summer"],
                                "risk_flags": [],
                                "evidence_summary": "too short",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_elements(elements_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "element evidence_summary is outside the allowed taxonomy range",
        )
        self.assertEqual(error_context.exception.details["field"], "evidence_summary")
        self.assertEqual(error_context.exception.details["length"], len("too short"))

    def test_reject_invalid_summary_fixture(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        fixture_path = Path("tests/fixtures/evidence/dress/invalid-short-summary-elements.json")
        taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")

        with self.assertRaises(GenerationError) as error_context:
            load_elements(fixture_path, taxonomy_path=taxonomy_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "element evidence_summary is outside the allowed taxonomy range",
        )
        self.assertEqual(error_context.exception.details["path"], str(fixture_path))
        self.assertEqual(error_context.exception.details["index"], 0)
        self.assertEqual(error_context.exception.details["field"], "evidence_summary")
        self.assertEqual(error_context.exception.details["length"], len("too short"))

    def test_accepts_canonical_slot_preferences_and_matches_runtime(self) -> None:
        from temu_y2_women.evidence_repository import load_elements, load_strategy_templates, retrieve_candidates
        from temu_y2_women.models import NormalizedRequest

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            self._write_elements_store(
                elements_path,
                [
                    self._base_element(
                        evidence_summary="Known silhouette used to validate canonical strategy preferences."
                    )
                ],
            )
            strategies_path = temp_root / "strategy_templates.json"
            self._write_strategy_store(
                strategies_path,
                [
                    self._base_strategy(
                        boost_tags=[],
                        slot_preferences={"silhouette": ["  A-LINE  "]},
                    )
                ],
            )

            strategy_records = load_strategy_templates(
                strategies_path,
                taxonomy_path=taxonomy_path,
                elements_path=elements_path,
            )
            elements = load_elements(elements_path, taxonomy_path=taxonomy_path)

        request = NormalizedRequest(
            category="dress",
            target_market="US",
            target_launch_date=date(2026, 6, 1),
            mode="A",
            price_band="mid",
            occasion_tags=(),
            must_have_tags=(),
            avoid_tags=(),
        )
        selected = self._to_selected_strategy(strategy_records[0], "canonical preference test")

        grouped, warnings = retrieve_candidates(request, elements, (selected,))

        self.assertEqual(warnings, ())
        self.assertEqual(grouped["silhouette"][0]["effective_score"], 0.85)

    def test_reject_unknown_strategy_slot_preference(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_strategy_templates

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            self._write_elements_store(
                elements_path,
                [
                    self._base_element(
                        evidence_summary="Known silhouette used to validate strategy references."
                    )
                ],
            )
            strategies_path = temp_root / "strategy_templates.json"
            self._write_strategy_store(
                strategies_path,
                [self._base_strategy(slot_preferences={"silhouette": ["unknown-shape"]})],
            )

            with self.assertRaises(GenerationError) as error_context:
                load_strategy_templates(
                    strategies_path,
                    taxonomy_path=taxonomy_path,
                    elements_path=elements_path,
                )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "strategy slot_preferences references unknown active element values",
        )
        self.assertEqual(error_context.exception.details["field"], "slot_preferences")
        self.assertEqual(error_context.exception.details["values"], ["unknown-shape"])

    def test_accepts_inactive_invalid_strategy_record(self) -> None:
        from temu_y2_women.evidence_repository import load_strategy_templates

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "evidence_taxonomy.json"
            self._write_taxonomy(taxonomy_path)
            elements_path = temp_root / "elements.json"
            self._write_elements_store(
                elements_path,
                [
                    self._base_element(
                        evidence_summary="Known silhouette used to isolate inactive strategy validation."
                    )
                ],
            )
            strategies_path = temp_root / "strategy_templates.json"
            self._write_strategy_store(
                strategies_path,
                [
                    self._base_strategy(
                        strategy_id="dress-us-inactive-broken",
                        boost_tags=["unknown-tag"],
                        slot_preferences={"silhouette": ["unknown-shape"]},
                        prompt_hints=["inactive"],
                        reason_template="inactive draft",
                        status="inactive",
                    )
                ],
            )

            strategies = load_strategy_templates(
                strategies_path,
                taxonomy_path=taxonomy_path,
                elements_path=elements_path,
            )

        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0]["status"], "inactive")

    def test_reject_invalid_strategy_slot_preference_fixture(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_strategy_templates

        fixture_path = Path("tests/fixtures/evidence/dress/invalid-strategy-slot-preference.json")
        taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")
        with TemporaryDirectory() as temp_dir:
            elements_path = Path(temp_dir) / "elements.json"
            elements_path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "elements": [
                            {
                                "element_id": "dress-neckline-square-001",
                                "category": "dress",
                                "slot": "neckline",
                                "value": "square neckline",
                                "tags": ["summer", "romantic", "feminine"],
                                "base_score": 0.73,
                                "price_bands": ["mid"],
                                "occasion_tags": ["casual"],
                                "season_tags": ["spring", "summer"],
                                "risk_flags": [],
                                "evidence_summary": "Known neckline fixture used to isolate strategy preference validation.",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_strategy_templates(
                    fixture_path,
                    taxonomy_path=taxonomy_path,
                    elements_path=elements_path,
                )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "strategy slot_preferences references unknown active element values",
        )
        self.assertEqual(error_context.exception.details["path"], str(fixture_path))
        self.assertEqual(error_context.exception.details["index"], 0)
        self.assertEqual(error_context.exception.details["field"], "slot_preferences")
        self.assertEqual(error_context.exception.details["slot"], "neckline")
        self.assertEqual(error_context.exception.details["values"], ["unknown-neckline"])

    def test_runtime_dress_evidence_includes_objective_slots(self) -> None:
        from temu_y2_women.evidence_repository import load_elements, load_strategy_templates

        taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")
        elements_path = Path("data/mvp/dress/elements.json")
        strategies_path = Path("data/mvp/dress/strategy_templates.json")

        elements = load_elements(elements_path, taxonomy_path=taxonomy_path)
        active_by_slot: dict[str, set[str]] = {}
        for element in elements:
            if element["status"] != "active":
                continue
            active_by_slot.setdefault(str(element["slot"]), set()).add(str(element["value"]))

        expected_slots = {
            "dress_length": {"mini", "midi"},
            "waistline": {"natural waist", "drop waist"},
            "color_family": {"white", "red"},
            "print_scale": {"micro print", "oversized print"},
            "opacity_level": {"opaque", "sheer"},
        }
        for slot, values in expected_slots.items():
            self.assertEqual(active_by_slot[slot], values)
        self.assertIn("polka dot", active_by_slot["pattern"])
        self.assertIn("neck scarf", active_by_slot["detail"])

        strategies = load_strategy_templates(
            strategies_path,
            taxonomy_path=taxonomy_path,
            elements_path=elements_path,
        )
        vacation = next(
            item for item in strategies if item["strategy_id"] == "dress-us-summer-vacation"
        )
        self.assertEqual(vacation["slot_preferences"]["dress_length"], ["mini", "midi"])
        self.assertEqual(vacation["slot_preferences"]["waistline"], ["drop waist"])
        self.assertEqual(vacation["slot_preferences"]["color_family"], ["white", "red"])
