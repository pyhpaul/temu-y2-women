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


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
