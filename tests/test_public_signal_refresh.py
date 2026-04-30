from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import unittest


_SOURCE_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")
_REFRESH_FIXTURE_DIR = Path("tests/fixtures/public_refresh/dress")


class PublicSignalRefreshTest(unittest.TestCase):
    def test_run_public_signal_refresh_writes_fetch_cache_and_fetch_artifacts(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        source_id = "whowhatwear-summer-2025-dress-trends"
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_single_source_registry()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_fixture_fetcher(),
            )
            run_dir = temp_root / result["run_id"]
            cache_meta = _read_json(temp_root / "fetch_cache" / f"{source_id}.json")
            fetch_meta = _read_json(run_dir / "fetched_sources" / f"{source_id}.json")
            self.assertTrue((temp_root / "fetch_cache" / f"{source_id}.html").exists())
            self.assertTrue((run_dir / "fetched_sources" / f"{source_id}.html").exists())
            self.assertEqual(cache_meta["fetch_status"], "live")
            self.assertEqual(fetch_meta["fetch_status"], "live")
            self.assertEqual(cache_meta["content_sha256"], fetch_meta["content_sha256"])

    def test_run_public_signal_refresh_uses_cached_html_when_fetch_fails(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        source_id = "whowhatwear-summer-2025-dress-trends"
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            cache_root = temp_root / "cache"
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_single_source_registry()), encoding="utf-8")
            first = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_fixture_fetcher(),
                cache_root=cache_root,
            )
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-29T00:00:00Z",
                fetcher=_always_failing_fetcher,
                cache_root=cache_root,
            )
            run_dir = temp_root / result["run_id"]
            fetch_meta = _read_json(run_dir / "fetched_sources" / f"{source_id}.json")
            self.assertEqual(result["source_summary"], {"total": 1, "succeeded": 1, "failed": 0})
            self.assertEqual(result["canonical_signal_count"], first["canonical_signal_count"])
            self.assertEqual(fetch_meta["fetch_status"], "cache_fallback")
            self.assertEqual(fetch_meta["cache_fetched_at"], "2026-04-28T00:00:00Z")
            self.assertEqual(fetch_meta["error_message"], "network timeout")

    def test_run_public_signal_refresh_writes_expected_staged_artifacts(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_single_source_registry()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_fixture_fetcher(),
            )
            run_dir = temp_root / result["run_id"]

            _assert_refresh_artifacts(self, run_dir, registry_path)

        self.assertEqual(result, _read_json(_REFRESH_FIXTURE_DIR / "expected-refresh-report.json"))

    def test_run_public_signal_refresh_does_not_mutate_active_runtime_evidence(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        elements_path = Path("data/mvp/dress/elements.json")
        strategies_path = Path("data/mvp/dress/strategy_templates.json")
        before_elements = elements_path.read_text(encoding="utf-8")
        before_strategies = strategies_path.read_text(encoding="utf-8")

        with TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "registry.json"
            registry_path.write_text(json.dumps(_single_source_registry()), encoding="utf-8")
            run_public_signal_refresh(
                registry_path=registry_path,
                output_root=Path(temp_dir),
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_fixture_fetcher(),
            )

        self.assertEqual(elements_path.read_text(encoding="utf-8"), before_elements)
        self.assertEqual(strategies_path.read_text(encoding="utf-8"), before_strategies)

    def test_run_public_signal_refresh_records_source_errors_but_allows_other_sources(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        def flaky_fetcher(url: str) -> str:
            if "whowhatwear" in url:
                return _fixture_html()
            raise OSError("network timeout")

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_registry_with_broken_source()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=flaky_fetcher,
            )

        self.assertEqual(result["source_summary"]["succeeded"], 1)
        self.assertEqual(result["source_summary"]["failed"], 1)
        self.assertEqual(result["selected_source_ids"], ["whowhatwear-summer-2025-dress-trends", "broken-source"])
        self.assertEqual(result["source_details"][0]["status"], "succeeded")
        self.assertEqual(result["source_details"][1]["status"], "failed")
        self.assertTrue(any(item["source_id"] == "broken-source" and item["stage"] == "fetch" for item in result["errors"]))

    def test_run_public_signal_refresh_can_target_single_source_id(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        def flaky_fetcher(url: str) -> str:
            if "whowhatwear.com" in url:
                return _fixture_html()
            raise OSError("network timeout")

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_registry_with_broken_source()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=flaky_fetcher,
                source_ids=["whowhatwear-summer-2025-dress-trends"],
            )

        self.assertEqual(result["source_summary"], {"total": 1, "succeeded": 1, "failed": 0})
        self.assertEqual(result["selected_source_ids"], ["whowhatwear-summer-2025-dress-trends"])
        self.assertEqual(len(result["source_details"]), 1)
        self.assertFalse(result["errors"])

    def test_run_public_signal_refresh_supports_all_configured_sources(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            result = run_public_signal_refresh(
                registry_path=Path("data/refresh/dress/source_registry.json"),
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_full_registry_fetcher(),
                card_image_observer=_fake_card_observer,
            )
            run_dir = temp_root / result["run_id"]
            second_whowhatwear_exists = (run_dir / "raw_sources" / "whowhatwear-summer-dress-trends-2025.json").exists()
            vogue_exists = (run_dir / "raw_sources" / "vogue-spring-2025-dress-trends.json").exists()
            marieclaire_exists = (run_dir / "raw_sources" / "marieclaire-summer-2025-dress-trends.json").exists()
            roundup_exists = (run_dir / "raw_sources" / "whowhatwear-best-summer-dresses-2025.json").exists()
            observation_exists = (run_dir / "card_observations" / "whowhatwear-best-summer-dresses-2025.json").exists()
            hearst_roundup_exists = (run_dir / "raw_sources" / "harpersbazaar-best-summer-dresses-2025.json").exists()
            hearst_observation_exists = (
                run_dir / "card_observations" / "harpersbazaar-best-summer-dresses-2025.json"
            ).exists()

        self.assertEqual(result["source_summary"], {"total": 6, "succeeded": 6, "failed": 0})
        self.assertEqual(result["canonical_signal_count"], 32)
        self.assertEqual(result["coverage"]["matched_signals"], 30)
        self.assertEqual(
            result["selected_source_ids"],
            [
                "whowhatwear-summer-2025-dress-trends",
                "whowhatwear-summer-dress-trends-2025",
                "vogue-spring-2025-dress-trends",
                "marieclaire-summer-2025-dress-trends",
                "whowhatwear-best-summer-dresses-2025",
                "harpersbazaar-best-summer-dresses-2025",
            ],
        )
        self.assertEqual(
            [item["matched_signal_count"] for item in result["source_details"]],
            [5, 8, 8, 7, 1, 1],
        )
        self.assertTrue(second_whowhatwear_exists)
        self.assertTrue(vogue_exists)
        self.assertTrue(marieclaire_exists)
        self.assertTrue(roundup_exists)
        self.assertTrue(observation_exists)
        self.assertTrue(hearst_roundup_exists)
        self.assertTrue(hearst_observation_exists)

    def test_run_public_signal_refresh_merges_editorial_and_roundup_sources(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_mixed_registry_fetcher(),
                card_image_observer=_fake_card_observer,
            )
            run_dir = temp_root / result["run_id"]
            card_observations = _read_json(run_dir / "card_observations" / "whowhatwear-best-summer-dresses-2025.json")
            signal_bundle = _read_json(run_dir / "signal_bundle.json")

        self.assertEqual(card_observations["schema_version"], "public-card-observations-v1")
        self.assertEqual(result["source_summary"], {"total": 2, "succeeded": 2, "failed": 0})
        roundup_detail = next(
            item for item in result["source_details"] if item["source_id"] == "whowhatwear-best-summer-dresses-2025"
        )
        editorial_bundle_signal = next(
            item for item in signal_bundle["signals"] if item["signal_id"] == "whowhatwear-summer-2025-dress-trends-the-vacation-mini-001"
        )
        roundup_bundle_signal = next(
            item for item in signal_bundle["signals"] if item["signal_id"] == "whowhatwear-best-summer-dresses-2025-dress_length-mini-001"
        )
        self.assertEqual(roundup_detail["card_count_extracted"], 3)
        self.assertEqual(roundup_detail["card_count_observed"], 3)
        self.assertEqual(roundup_detail["aggregated_signal_count"], 1)
        self.assertEqual(roundup_detail["card_limit"], 12)
        self.assertEqual(roundup_detail["aggregation_threshold"], 2)
        self.assertNotIn("structured_candidates", editorial_bundle_signal)
        self.assertEqual(len(roundup_bundle_signal["structured_candidates"]), 1)
        self.assertEqual(
            roundup_bundle_signal["structured_candidates"][0]["candidate_source"],
            "roundup_card_image_aggregation",
        )

    def test_run_public_signal_refresh_promotes_new_structured_value_into_drafts(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-29T00:00:00Z",
                fetcher=_mixed_registry_fetcher(),
                card_image_observer=_fake_card_observer_with_new_value,
            )
            run_dir = temp_root / result["run_id"]
            draft_elements = _read_json(run_dir / "draft_elements.json")["elements"]
            ingestion_report = _read_json(run_dir / "ingestion_report.json")

        gingham = next(item for item in draft_elements if item["draft_id"] == "draft-pattern-gingham-check")
        outcome = next(
            item
            for item in ingestion_report["signal_outcomes"]
            if item["signal_id"] == "whowhatwear-best-summer-dresses-2025-pattern-gingham-check-001"
        )
        self.assertEqual(gingham["tags"], ["summer", "vacation"])
        self.assertEqual(gingham["suggested_base_score"], 0.7)
        self.assertEqual(gingham["extraction_provenance"]["kind"], "structured-signal-candidate")
        self.assertEqual(gingham["extraction_provenance"]["matched_channels"], ["structured_candidate"])
        self.assertEqual(outcome["matched_channels"], ["structured_candidate"])
        self.assertEqual(outcome["matched_structured_keys"], ["pattern:gingham check"])

    def test_run_public_signal_refresh_surfaces_structured_candidate_summary(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-29T00:00:00Z",
                fetcher=_mixed_registry_fetcher(),
                card_image_observer=_fake_card_observer_with_new_value,
            )

        roundup_detail = next(
            item for item in result["source_details"] if item["source_id"] == "whowhatwear-best-summer-dresses-2025"
        )
        self.assertEqual(
            result["structured_candidate_summary"],
            {
                "signal_count": 1,
                "candidate_count": 1,
                "matched_signal_count": 1,
                "matched_key_count": 1,
            },
        )
        self.assertEqual(
            roundup_detail["structured_candidate_summary"],
            {
                "candidate_count": 1,
                "matched_signal_count": 1,
                "matched_key_count": 1,
            },
        )


def _registry_with_broken_source() -> dict[str, object]:
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
                "source_id": "broken-source",
                "source_type": "public_editorial_web",
                "source_url": "https://example.com/broken",
                "target_market": "US",
                "category": "dress",
                "fetch_mode": "html",
                "adapter_id": "whowhatwear_editorial_v1",
                "default_price_band": "mid",
                "pipeline_mode": "editorial_text",
                "priority": 90,
                "weight": 0.8,
                "enabled": True,
            },
        ],
    }


def _single_source_registry() -> dict[str, object]:
    payload = _registry_with_broken_source()
    payload["sources"] = [payload["sources"][0]]
    return payload


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_html() -> str:
    return (_SOURCE_FIXTURE_DIR / "whowhatwear-summer-2025-dress-trends.html").read_text(encoding="utf-8")


def _fixture_fetcher() -> Callable[[str], str]:
    html = _fixture_html()

    def fetcher(_: str) -> str:
        return html

    return fetcher


def _always_failing_fetcher(_: str) -> str:
    raise OSError("network timeout")


def _full_registry_fetcher() -> Callable[[str], str]:
    html_by_url = {
        "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends": _fixture_html(),
        "https://www.whowhatwear.com/fashion/dresses/summer-dress-trends-2025": (
            _SOURCE_FIXTURE_DIR / "whowhatwear-summer-dress-trends-2025.html"
        ).read_text(encoding="utf-8"),
        "https://www.vogue.com/article/spring-2025-dress-trends": (
            _SOURCE_FIXTURE_DIR / "vogue-spring-2025-dress-trends.html"
        ).read_text(encoding="utf-8"),
        "https://www.marieclaire.com/fashion/summer-fashion/summer-2025-dress-trends/": (
            _SOURCE_FIXTURE_DIR / "marieclaire-summer-2025-dress-trends.html"
        ).read_text(encoding="utf-8"),
        "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025": (
            _SOURCE_FIXTURE_DIR / "whowhatwear-best-summer-dresses-2025.html"
        ).read_text(encoding="utf-8"),
        "https://www.harpersbazaar.com/fashion/trends/g65192976/best-summer-dresses-for-women/": (
            _SOURCE_FIXTURE_DIR / "harpersbazaar-best-summer-dresses-2025.html"
        ).read_text(encoding="utf-8"),
    }

    def fetcher(url: str) -> str:
        return html_by_url[url]

    return fetcher


def _fixture_fetcher_by_url() -> Callable[[str], str]:
    return _full_registry_fetcher()


def _mixed_source_registry() -> dict[str, object]:
    return {
        "schema_version": "public-source-registry-v1",
        "sources": [
            _single_source_registry()["sources"][0],
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
        "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends": _fixture_html(),
        "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025": (
            _SOURCE_FIXTURE_DIR / "whowhatwear-best-summer-dresses-2025.html"
        ).read_text(encoding="utf-8"),
    }

    def fetcher(url: str) -> str:
        return html_by_url[url]

    return fetcher


def _fake_card_observer(card: dict[str, object]) -> dict[str, object]:
    if str(card["card_id"]).endswith("001"):
        return {
            "observed_slots": [
                {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                {"slot": "color_family", "value": "white", "evidence_summary": "dress reads bright white"},
            ],
            "abstained_slots": ["waistline", "opacity_level"],
            "warnings": [],
        }
    if str(card["card_id"]).endswith("002"):
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
            {"slot": "waistline", "value": "drop waist", "evidence_summary": "seam sits below natural waist"}
        ],
        "abstained_slots": ["opacity_level"],
        "warnings": [],
    }


def _fake_card_observer_with_new_value(card: dict[str, object]) -> dict[str, object]:
    if str(card["card_id"]).endswith(("001", "002")):
        return {
            "observed_slots": [
                {"slot": "pattern", "value": "gingham check", "evidence_summary": "small two-tone checks repeat across the dress"},
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


def _assert_refresh_artifacts(test_case: unittest.TestCase, run_dir: Path, registry_path: Path) -> None:
    expected = {
        run_dir / "source_registry_snapshot.json": registry_path,
        run_dir / "raw_sources" / "whowhatwear-summer-2025-dress-trends.json": _SOURCE_FIXTURE_DIR / "expected-whowhatwear-raw-source-snapshot.json",
        run_dir / "canonical_signals.json": _SOURCE_FIXTURE_DIR / "expected-canonical-signals.json",
        run_dir / "signal_bundle.json": _SOURCE_FIXTURE_DIR / "expected-signal-bundle.json",
        run_dir / "draft_elements.json": _REFRESH_FIXTURE_DIR / "expected-draft-elements.json",
        run_dir / "draft_strategy_hints.json": _REFRESH_FIXTURE_DIR / "expected-draft-strategy-hints.json",
        run_dir / "normalized_signals.json": _REFRESH_FIXTURE_DIR / "expected-normalized-signals.json",
        run_dir / "ingestion_report.json": _REFRESH_FIXTURE_DIR / "expected-ingestion-report.json",
        run_dir / "refresh_report.json": _REFRESH_FIXTURE_DIR / "expected-refresh-report.json",
    }
    for actual_path, expected_path in expected.items():
        with test_case.subTest(path=str(actual_path.name)):
            test_case.assertEqual(_read_json(actual_path), _read_json(expected_path))
