from __future__ import annotations

import json
from pathlib import Path
import unittest


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class PublicCardObserverTest(unittest.TestCase):
    def test_observe_roundup_cards_keeps_only_whitelisted_slots_and_records_abstentions(self) -> None:
        from temu_y2_women.public_card_observer import observe_roundup_cards

        snapshot = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json")

        def fake_observer(card: dict[str, object]) -> dict[str, object]:
            if card["card_id"] == "whowhatwear-best-summer-dresses-2025-card-001":
                return {
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                        {"slot": "color_family", "value": "white", "evidence_summary": "dress reads bright white"},
                        {"slot": "unsupported_slot", "value": "ignore", "evidence_summary": "bad"},
                    ],
                    "abstained_slots": ["waistline", "opacity_level"],
                    "warnings": [],
                }
            if card["card_id"] == "whowhatwear-best-summer-dresses-2025-card-002":
                return {
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                        {"slot": "pattern", "value": "polka dot", "evidence_summary": "repeating dotted print"},
                    ],
                    "abstained_slots": ["opacity_level"],
                    "warnings": [],
                }
            return {
                "observed_slots": [
                    {"slot": "waistline", "value": "drop waist", "evidence_summary": "seam sits below natural waist"},
                    {"slot": "dress_length", "value": "midi", "evidence_summary": "hemline lands mid-calf"},
                ],
                "abstained_slots": ["opacity_level"],
                "warnings": ["pattern not clearly visible"],
            }

        result = observe_roundup_cards(
            snapshot=snapshot,
            observation_model="fake-roundup-observer",
            observe_card=fake_observer,
            card_limit=2,
        )

        expected = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-card-observations.json")
        self.assertEqual(result, expected)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
