from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class CanonicalSignalBuilderTest(unittest.TestCase):
    def test_builds_expected_canonical_signals_with_price_band_fallback(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals

        snapshot = _load_snapshot()
        result = build_canonical_signals(snapshot=snapshot, default_price_band="mid")

        expected = json.loads((_FIXTURE_DIR / "expected-canonical-signals.json").read_text(encoding="utf-8"))
        self.assertEqual(result, expected)

    def test_builds_signal_bundle_compatible_with_signal_ingestion(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals, build_signal_bundle

        snapshot = _load_snapshot()
        canonical_payload = build_canonical_signals(snapshot=snapshot, default_price_band="mid")
        result = build_signal_bundle(canonical_payload)

        expected = json.loads((_FIXTURE_DIR / "expected-signal-bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(result, expected)

    def test_bundle_can_flow_into_existing_signal_ingestion(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals, build_signal_bundle
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        snapshot = _load_snapshot()
        canonical_payload = build_canonical_signals(snapshot=snapshot, default_price_band="mid")
        signal_bundle = build_signal_bundle(canonical_payload)

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signal_bundle.json"
            input_path.write_text(json.dumps(signal_bundle), encoding="utf-8")
            result = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

        self.assertNotIn("error", result)
        self.assertEqual(
            result["coverage"]["matched_signal_ids"],
            [
                "whowhatwear-summer-2025-dress-trends-the-vacation-mini-001",
                "whowhatwear-summer-2025-dress-trends-fairy-sleeves-002",
            ],
        )

    def test_derives_canonical_fields_from_section_text_even_if_section_slug_changes(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals

        snapshot = _load_snapshot()
        snapshot["sections"][0]["section_id"] = "trend-001"

        result = build_canonical_signals(snapshot=snapshot, default_price_band="mid")
        signal = result["signals"][0]

        self.assertEqual(signal["canonical_signal_id"], "whowhatwear-summer-2025-dress-trends-trend-001-001")
        self.assertEqual(
            signal["evidence_excerpt"],
            "smocked bodices, halter ties, and prints that look like they belong in a cocktail glass",
        )
        self.assertEqual(signal["manual_tags"], ["summer", "vacation"])
        self.assertEqual(
            signal["extraction_provenance"]["matched_keywords"],
            ["smocked bodices", "halter ties", "prints", "vacation mini"],
        )

    def test_rejects_section_missing_required_fields_with_generation_error(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals
        from temu_y2_women.errors import GenerationError

        snapshot = _load_snapshot()
        del snapshot["sections"][0]["heading"]

        with self.assertRaises(GenerationError) as error:
            build_canonical_signals(snapshot=snapshot, default_price_band="mid")

        self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
        self.assertEqual(error.exception.details["field"], "section.heading")

    def test_rejects_invalid_snapshot_schema_version(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals
        from temu_y2_women.errors import GenerationError

        snapshot = _load_snapshot()
        snapshot["schema_version"] = "legacy-snapshot-v1"

        with self.assertRaises(GenerationError) as error:
            build_canonical_signals(snapshot=snapshot, default_price_band="mid")

        self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
        self.assertEqual(error.exception.details["field"], "snapshot.schema_version")

    def test_rejects_invalid_canonical_payload_with_generation_error(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_signal_bundle
        from temu_y2_women.errors import GenerationError

        payload = _valid_canonical_payload()
        del payload["signals"][0]["source_type"]

        with self.assertRaises(GenerationError) as error:
            build_signal_bundle(payload)

        self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
        self.assertEqual(error.exception.details["field"], "signal.source_type")

    def test_rejects_invalid_canonical_schema_version(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_signal_bundle
        from temu_y2_women.errors import GenerationError

        payload = _valid_canonical_payload()
        payload["schema_version"] = "legacy-signals-v1"

        with self.assertRaises(GenerationError) as error:
            build_signal_bundle(payload)

        self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
        self.assertEqual(error.exception.details["field"], "schema_version")

    def test_rejects_invalid_observed_price_band_in_canonical_signal(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_signal_bundle
        from temu_y2_women.errors import GenerationError

        payload = _valid_canonical_payload()
        payload["signals"][0]["observed_price_band"] = "luxury"

        with self.assertRaises(GenerationError) as error:
            build_signal_bundle(payload)

        self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
        self.assertEqual(error.exception.details["field"], "signal.observed_price_band")

    def test_accepts_supported_price_band_resolution_values(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_signal_bundle

        for resolution in ("observed", "rule_fallback", "source_default"):
            payload = _valid_canonical_payload()
            payload["signals"][0]["price_band_resolution"] = resolution

            with self.subTest(resolution=resolution):
                result = build_signal_bundle(payload)
                self.assertEqual(result["signals"][0]["signal_id"], "signal-001")

    def test_rejects_missing_canonical_contract_fields_before_bundle_build(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_signal_bundle
        from temu_y2_women.errors import GenerationError

        for field in ("source_id", "fetched_at", "evidence_excerpt", "price_band_resolution"):
            payload = _valid_canonical_payload()
            del payload["signals"][0][field]

            with self.subTest(field=field):
                with self.assertRaises(GenerationError) as error:
                    build_signal_bundle(payload)

                self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
                self.assertEqual(error.exception.details["field"], f"signal.{field}")

    def test_rejects_boolean_confidence_in_provenance(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_signal_bundle
        from temu_y2_women.errors import GenerationError

        payload = _valid_canonical_payload()
        payload["signals"][0]["extraction_provenance"]["confidence"] = True

        with self.assertRaises(GenerationError) as error:
            build_signal_bundle(payload)

        self.assertEqual(error.exception.code, "INVALID_CANONICAL_SIGNAL_INPUT")
        self.assertEqual(error.exception.details["field"], "signal.extraction_provenance.confidence")

    def test_phrase_rule_aliases_cover_public_editorial_variants(self) -> None:
        rules = json.loads(Path("data/ingestion/dress/signal_phrase_rules.json").read_text(encoding="utf-8"))
        by_value = {rule["value"]: rule for rule in rules["slot_value_rules"]}

        self.assertIn("fairy sleeves", by_value["flutter sleeve"]["phrases"])
        self.assertIn("smocked bodices", by_value["smocked bodice"]["phrases"])

    def test_normalizes_source_tag_case_and_whitespace(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals

        snapshot = _load_snapshot()
        snapshot["sections"][0]["tags"] = [" Summer ", "Vacation"]

        result = build_canonical_signals(snapshot=snapshot, default_price_band="mid")
        signal = result["signals"][0]

        self.assertEqual(signal["observed_season_tags"], ["summer"])
        self.assertEqual(signal["observed_occasion_tags"], ["vacation"])
        self.assertEqual(signal["manual_tags"], ["summer", "vacation"])

    def test_uses_section_metadata_for_provenance_when_present(self) -> None:
        from temu_y2_women.canonical_signal_builder import build_canonical_signals

        snapshot = _load_snapshot()
        snapshot["sections"][0]["matched_keywords"] = ["custom keyword"]
        snapshot["sections"][0]["confidence"] = 0.91
        snapshot["sections"][0]["adapter_version"] = "custom_editorial_v1"
        snapshot["sections"][0]["warnings"] = ["custom warning"]
        snapshot["sections"][0]["excerpt_anchor"] = "halter ties"

        result = build_canonical_signals(snapshot=snapshot, default_price_band="mid")
        signal = result["signals"][0]

        self.assertEqual(
            signal["evidence_excerpt"],
            "halter ties, and prints that look like they belong in a cocktail glass",
        )
        self.assertEqual(signal["extraction_provenance"]["matched_keywords"], ["custom keyword"])
        self.assertEqual(signal["extraction_provenance"]["adapter_version"], "custom_editorial_v1")
        self.assertEqual(signal["extraction_provenance"]["warnings"], ["custom warning"])
        self.assertEqual(signal["extraction_provenance"]["confidence"], 0.91)


def _load_snapshot() -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / "expected-whowhatwear-raw-source-snapshot.json").read_text(encoding="utf-8"))


def _valid_canonical_payload() -> dict[str, object]:
    return {
        "schema_version": "canonical-signals-v1",
        "signals": [
            {
                "canonical_signal_id": "signal-001",
                "source_id": "whowhatwear-summer-2025-dress-trends",
                "source_type": "public_editorial_web",
                "source_url": "https://example.com",
                "captured_at": "2025-06-18",
                "fetched_at": "2026-04-28T00:00:00Z",
                "target_market": "US",
                "category": "dress",
                "title": "Signal title",
                "summary": "Signal summary",
                "evidence_excerpt": "Signal evidence excerpt",
                "observed_price_band": "mid",
                "price_band_resolution": "source_default",
                "observed_occasion_tags": [],
                "observed_season_tags": ["summer"],
                "manual_tags": ["summer"],
                "status": "active",
                "extraction_provenance": {
                    "source_section": "section-001",
                    "matched_keywords": ["signal"],
                    "adapter_version": "whowhatwear_editorial_v1",
                    "warnings": ["price band defaulted from source registry"],
                    "confidence": 0.65,
                },
            }
        ],
    }
