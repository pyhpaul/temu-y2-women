from __future__ import annotations

import json
from pathlib import Path
import unittest


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class RoundupCanonicalSignalBuilderTest(unittest.TestCase):
    def test_build_roundup_canonical_signals_aggregates_repeated_slot_values(self) -> None:
        from temu_y2_women.roundup_canonical_signal_builder import build_roundup_canonical_signals

        snapshot = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json")
        observations = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-card-observations.json")

        result = build_roundup_canonical_signals(
            snapshot=snapshot,
            observations=observations,
            default_price_band="mid",
            aggregation_threshold=2,
        )

        expected = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json")
        self.assertEqual(result, expected)

    def test_build_roundup_canonical_signals_emits_structured_candidates(self) -> None:
        from temu_y2_women.roundup_canonical_signal_builder import build_roundup_canonical_signals

        snapshot = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json")
        observations = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-card-observations.json")

        result = build_roundup_canonical_signals(
            snapshot=snapshot,
            observations=observations,
            default_price_band="mid",
            aggregation_threshold=2,
        )

        candidate = result["signals"][0]["structured_candidates"][0]
        self.assertEqual(candidate["candidate_source"], "roundup_card_image_aggregation")
        self.assertEqual(candidate["slot"], "dress_length")
        self.assertEqual(candidate["value"], "mini")
        self.assertEqual(
            candidate["supporting_card_ids"],
            [
                "whowhatwear-best-summer-dresses-2025-card-001",
                "whowhatwear-best-summer-dresses-2025-card-002",
            ],
        )
        self.assertEqual(candidate["supporting_card_count"], 2)
        self.assertEqual(candidate["aggregation_threshold"], 2)
        self.assertEqual(candidate["observation_model"], "fake-roundup-observer")
        self.assertIn("hemline ends above knee", candidate["evidence_summary"])

    def test_build_roundup_canonical_signals_uses_snapshot_adapter_version_when_present(self) -> None:
        from temu_y2_women.roundup_canonical_signal_builder import build_roundup_canonical_signals

        snapshot = _read_json(_FIXTURE_DIR / "expected-harpersbazaar-best-summer-dresses-2025-raw-source-snapshot.json")
        snapshot["adapter_version"] = "hearst_roundup_v1"
        observations = {
            "schema_version": "public-card-observations-v1",
            "source_id": snapshot["source_id"],
            "source_url": snapshot["source_url"],
            "fetched_at": snapshot["fetched_at"],
            "observation_model": "fake-roundup-observer",
            "card_limit": 12,
            "cards": [
                {
                    **snapshot["cards"][0],
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"}
                    ],
                    "abstained_slots": [],
                    "warnings": [],
                },
                {
                    **snapshot["cards"][1],
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"}
                    ],
                    "abstained_slots": [],
                    "warnings": [],
                },
            ],
        }

        result = build_roundup_canonical_signals(
            snapshot=snapshot,
            observations=observations,
            default_price_band="mid",
            aggregation_threshold=2,
        )

        self.assertEqual(result["signals"][0]["extraction_provenance"]["adapter_version"], "hearst_roundup_v1")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
