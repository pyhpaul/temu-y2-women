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
                _read_json(_SIGNAL_FIXTURE_DIR / "expected-draft-elements.json"),
            )
            self.assertEqual(
                _read_json(output_dir / "draft_strategy_hints.json"),
                _read_json(_SIGNAL_FIXTURE_DIR / "expected-draft-strategy-hints.json"),
            )
            self.assertEqual(
                _read_json(output_dir / "ingestion_report.json"),
                _read_json(_SIGNAL_FIXTURE_DIR / "expected-ingestion-report.json"),
            )

        self.assertEqual(report, _read_json(_SIGNAL_FIXTURE_DIR / "expected-ingestion-report.json"))

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
        neckline = next(item for item in draft_elements if item["draft_id"] == "draft-neckline-square-neckline")
        pattern = next(item for item in draft_elements if item["draft_id"] == "draft-pattern-floral-print")
        sleeve = next(item for item in draft_elements if item["draft_id"] == "draft-sleeve-flutter-sleeve")
        hint = strategy_hints[0]
        self.assertIn("extraction_provenance", fabric)
        self.assertIn("rule_matches", fabric["extraction_provenance"])
        self.assertIn("extraction_provenance", hint)
        self.assertIn("source_draft_ids", hint["extraction_provenance"])
        self.assertEqual(
            neckline["extraction_provenance"]["rule_matches"][0]["matched_phrases"],
            ["square neckline"],
        )
        self.assertEqual(
            pattern["extraction_provenance"]["rule_matches"][0]["matched_phrases"],
            ["floral print"],
        )
        self.assertEqual(
            sleeve["extraction_provenance"]["rule_matches"][0]["matched_phrases"],
            ["flutter sleeves"],
        )

    def test_ingest_dress_signals_emits_new_objective_slot_drafts(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            ingest_dress_signals(
                input_path=_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json",
                output_dir=output_dir,
            )
            draft_elements = _read_json(output_dir / "draft_elements.json")["elements"]

        actual_pairs = {(item["slot"], item["value"]) for item in draft_elements}
        expected_pairs = {
            ("dress_length", "mini"),
            ("color_family", "white"),
            ("print_scale", "micro print"),
            ("opacity_level", "sheer"),
            ("waistline", "drop waist"),
        }
        self.assertTrue(expected_pairs.issubset(actual_pairs))

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
        unmatched = next(item for item in report["signal_outcomes"] if item["signal_id"] == "dress-signal-003")
        self.assertEqual(unmatched["status"], "unmatched")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
