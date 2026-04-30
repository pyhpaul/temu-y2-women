from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_SIGNAL_FIXTURE_DIR = Path("tests/fixtures/signals/dress")


class SignalIngestionTest(unittest.TestCase):
    def test_ingest_dress_signals_writes_expected_staged_artifacts(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = ingest_dress_signals(
                input_path=_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json",
                output_dir=output_dir,
            )

            self.assertEqual(
                _read_json(output_dir / "normalized_signals.json"),
                _read_json(_SIGNAL_FIXTURE_DIR / "expected-normalized-signals.json"),
            )
            self.assertEqual(
                _read_json(output_dir / "draft_elements.json"),
                _expected_draft_elements_fixture(),
            )
            self.assertEqual(
                _read_json(output_dir / "draft_strategy_hints.json"),
                _read_json(_SIGNAL_FIXTURE_DIR / "expected-draft-strategy-hints.json"),
            )
            self.assertEqual(
                _read_json(output_dir / "ingestion_report.json"),
                _expected_ingestion_report_fixture(),
            )

        self.assertEqual(report, _expected_ingestion_report_fixture())

    def test_ingest_dress_signals_rejects_invalid_signal_bundle(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            result = ingest_dress_signals(
                input_path=_SIGNAL_FIXTURE_DIR / "invalid-signal-bundle.json",
                output_dir=output_dir,
            )

        self.assertEqual(result["error"]["code"], "INVALID_SIGNAL_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "category")
        self.assertEqual(result["error"]["details"]["value"], "top")

    def test_ingestion_does_not_mutate_active_runtime_evidence_files(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        elements_path = Path("data/mvp/dress/elements.json")
        strategies_path = Path("data/mvp/dress/strategy_templates.json")
        before_elements = elements_path.read_text(encoding="utf-8")
        before_strategies = strategies_path.read_text(encoding="utf-8")

        with TemporaryDirectory() as temp_dir:
            ingest_dress_signals(
                input_path=_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json",
                output_dir=Path(temp_dir),
            )

        self.assertEqual(elements_path.read_text(encoding="utf-8"), before_elements)
        self.assertEqual(strategies_path.read_text(encoding="utf-8"), before_strategies)

    def test_ingest_dress_signals_records_provenance_in_staged_drafts(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            ingest_dress_signals(
                input_path=_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json",
                output_dir=output_dir,
            )

            draft_elements = _read_json(output_dir / "draft_elements.json")["elements"]
            strategy_hints = _read_json(output_dir / "draft_strategy_hints.json")["strategy_hints"]

        fabric = next(item for item in draft_elements if item["draft_id"] == "draft-fabric-cotton-poplin")
        hint = strategy_hints[0]
        self.assertIn("extraction_provenance", fabric)
        self.assertIn("rule_matches", fabric["extraction_provenance"])
        self.assertIn("extraction_provenance", hint)
        self.assertIn("source_draft_ids", hint["extraction_provenance"])

    def test_ingest_dress_signals_reports_coverage_and_unmatched_signals(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signals.json"
            bundle = _read_json(_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json")
            bundle["signals"].append(
                {
                    "signal_id": "dress-signal-003",
                    "source_type": "manual_import",
                    "source_url": "https://example.com/source-003",
                    "captured_at": "2026-04-22",
                    "target_market": "US",
                    "category": "dress",
                    "title": "Relaxed resort midi dress",
                    "summary": "Soft drape dress with sun-faded color story and easy pull-on shape.",
                    "observed_price_band": "mid",
                    "observed_occasion_tags": ["resort"],
                    "observed_season_tags": ["summer"],
                    "manual_tags": ["vacation", "lightweight"],
                    "status": "active",
                }
            )
            input_path.write_text(json.dumps(bundle), encoding="utf-8")
            report = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

        self.assertIn("coverage", report)
        self.assertEqual(report["coverage"]["unmatched_signal_ids"], ["dress-signal-003"])
        self.assertIn("signal_outcomes", report)
        self.assertEqual(report["signal_outcomes"][-1]["status"], "unmatched")
        self.assertEqual(report["signal_outcomes"][-1]["matched_channels"], [])

    def test_ingest_dress_signals_rejects_invalid_structured_candidates(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signals.json"
            bundle = _read_json(_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json")
            bundle["signals"][0]["structured_candidates"] = [
                {
                    "slot": "waist",
                    "value": "Waist Tie",
                    "candidate_source": "image-vision-v1",
                    "supporting_card_ids": ["card-001"],
                    "supporting_card_count": 1,
                    "aggregation_threshold": 1,
                    "observation_model": "gpt-image-structured-v1",
                    "evidence_summary": "Structured candidate summary long enough for deterministic validation.",
                }
            ]
            input_path.write_text(json.dumps(bundle), encoding="utf-8")
            result = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

        self.assertEqual(result["error"]["code"], "INVALID_SIGNAL_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "structured_candidates.slot")
        self.assertEqual(result["error"]["details"]["value"], "waist")

    def test_ingest_dress_signals_emits_structured_candidates_for_new_values(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signals.json"
            bundle = _read_json(_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json")
            bundle["signals"][0]["structured_candidates"] = [
                {
                    "slot": "detail",
                    "value": " Waist Tie ",
                    "candidate_source": "image-vision-v1",
                    "supporting_card_ids": ["card-002", "card-001", "card-002"],
                    "supporting_card_count": 2,
                    "aggregation_threshold": 2,
                    "observation_model": "gpt-image-structured-v1",
                    "evidence_summary": "Waist ties give lightweight summer dresses a clear shape cue without losing vacation ease.",
                }
            ]
            input_path.write_text(json.dumps(bundle), encoding="utf-8")
            ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")
            draft_elements = _read_json(temp_root / "staged" / "draft_elements.json")["elements"]
            report = _read_json(temp_root / "staged" / "ingestion_report.json")

        waist_tie = next(item for item in draft_elements if item["draft_id"] == "draft-detail-waist-tie")
        self.assertEqual(waist_tie["value"], "waist tie")
        self.assertEqual(waist_tie["tags"], [])
        self.assertEqual(
            waist_tie["evidence_summary"],
            (
                "2 cards agree on detail=waist tie: "
                "Waist ties give lightweight summer dresses a clear shape cue without losing vacation ease."
            ),
        )
        self.assertEqual(waist_tie["extraction_provenance"]["kind"], "structured-signal-candidate")
        self.assertEqual(waist_tie["extraction_provenance"]["matched_channels"], ["structured_candidate"])
        self.assertEqual(report["signal_outcomes"][0]["matched_channels"], ["structured_candidate", "text_rule"])

    def test_ingest_dress_signals_marks_hybrid_provenance_when_both_channels_match(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signals.json"
            bundle = _read_json(_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json")
            bundle["signals"][0]["structured_candidates"] = [
                {
                    "slot": "fabric",
                    "value": "Cotton Poplin",
                    "candidate_source": "image-vision-v1",
                    "supporting_card_ids": ["card-010"],
                    "supporting_card_count": 1,
                    "aggregation_threshold": 1,
                    "observation_model": "gpt-image-structured-v1",
                    "evidence_summary": "Cotton poplin keeps summer dresses crisp, breathable, and easy to pack for vacation.",
                }
            ]
            input_path.write_text(json.dumps(bundle), encoding="utf-8")
            ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")
            draft_elements = _read_json(temp_root / "staged" / "draft_elements.json")["elements"]

        fabric = next(item for item in draft_elements if item["draft_id"] == "draft-fabric-cotton-poplin")
        self.assertEqual(fabric["tags"], ["lightweight", "summer", "vacation"])
        self.assertEqual(fabric["extraction_provenance"]["kind"], "hybrid-signal-candidate")
        self.assertEqual(fabric["extraction_provenance"]["matched_channels"], ["structured_candidate", "text_rule"])
        self.assertIn("rule_matches", fabric["extraction_provenance"])
        self.assertIn("structured_candidate_matches", fabric["extraction_provenance"])

    def test_ingest_dress_signals_clamps_suggested_base_score_to_taxonomy_max(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signals.json"
            bundle = {
                "schema_version": "signal-bundle-v1",
                "signals": [_mini_signal(index) for index in range(1, 10)],
            }
            input_path.write_text(json.dumps(bundle), encoding="utf-8")
            ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")
            draft_elements = _read_json(temp_root / "staged" / "draft_elements.json")["elements"]

        mini = next(item for item in draft_elements if item["draft_id"] == "draft-dress_length-mini")
        self.assertEqual(mini["suggested_base_score"], 1.0)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mini_signal(index: int) -> dict[str, object]:
    return {
        "signal_id": f"mini-signal-{index:03d}",
        "source_type": "manual_import",
        "source_url": f"https://example.com/source-{index:03d}",
        "captured_at": "2026-04-22",
        "target_market": "US",
        "category": "dress",
        "title": f"Mini dress signal {index}",
        "summary": "Summer mini dress demand signal.",
        "observed_price_band": "mid",
        "observed_occasion_tags": ["vacation"],
        "observed_season_tags": ["summer"],
        "manual_tags": ["summer"],
        "status": "active",
    }


def _expected_draft_elements_fixture() -> dict[str, object]:
    payload = _read_json(_SIGNAL_FIXTURE_DIR / "expected-draft-elements.json")
    for element in payload["elements"]:
        element["extraction_provenance"]["matched_channels"] = ["text_rule"]
    return payload


def _expected_ingestion_report_fixture() -> dict[str, object]:
    payload = _read_json(_SIGNAL_FIXTURE_DIR / "expected-ingestion-report.json")
    for outcome in payload["signal_outcomes"]:
        outcome["matched_structured_keys"] = []
        outcome["matched_channels"] = ["text_rule"]
    return payload
