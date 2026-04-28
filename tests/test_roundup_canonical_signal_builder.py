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


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
