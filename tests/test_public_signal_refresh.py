from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import unittest


_SOURCE_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")
_REFRESH_FIXTURE_DIR = Path("tests/fixtures/public_refresh/dress")


class PublicSignalRefreshTest(unittest.TestCase):
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
            )
            run_dir = temp_root / result["run_id"]
            second_whowhatwear_exists = (run_dir / "raw_sources" / "whowhatwear-summer-dress-trends-2025.json").exists()
            marieclaire_exists = (run_dir / "raw_sources" / "marieclaire-summer-2025-dress-trends.json").exists()

        self.assertEqual(result["source_summary"], {"total": 3, "succeeded": 3, "failed": 0})
        self.assertEqual(result["canonical_signal_count"], 15)
        self.assertEqual(result["coverage"]["matched_signals"], 14)
        self.assertEqual(
            result["selected_source_ids"],
            [
                "whowhatwear-summer-2025-dress-trends",
                "whowhatwear-summer-dress-trends-2025",
                "marieclaire-summer-2025-dress-trends",
            ],
        )
        self.assertEqual(
            [item["matched_signal_count"] for item in result["source_details"]],
            [5, 5, 4],
        )
        self.assertTrue(second_whowhatwear_exists)
        self.assertTrue(marieclaire_exists)


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


def _full_registry_fetcher() -> Callable[[str], str]:
    html_by_url = {
        "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends": _fixture_html(),
        "https://www.whowhatwear.com/fashion/dresses/summer-dress-trends-2025": (
            _SOURCE_FIXTURE_DIR / "whowhatwear-summer-dress-trends-2025.html"
        ).read_text(encoding="utf-8"),
        "https://www.marieclaire.com/fashion/summer-fashion/summer-2025-dress-trends/": (
            _SOURCE_FIXTURE_DIR / "marieclaire-summer-2025-dress-trends.html"
        ).read_text(encoding="utf-8"),
    }

    def fetcher(url: str) -> str:
        return html_by_url[url]

    return fetcher


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
