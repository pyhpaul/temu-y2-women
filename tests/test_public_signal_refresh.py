from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import unittest


_SOURCE_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class PublicSignalRefreshTest(unittest.TestCase):
    def test_run_public_signal_refresh_writes_expected_staged_artifacts(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            result = run_public_signal_refresh(
                registry_path=Path("data/refresh/dress/source_registry.json"),
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_fixture_fetcher_by_url(),
            )
            run_dir = temp_root / result["run_id"]

            self.assertEqual(result["source_summary"], {"total": 2, "succeeded": 2, "failed": 0})
            self.assertEqual(result["canonical_signal_count"], 12)
            self.assertEqual(result["signal_bundle_count"], 12)
            self.assertTrue((run_dir / "raw_sources" / "whowhatwear-summer-2025-dress-trends.json").exists())
            self.assertTrue((run_dir / "raw_sources" / "marieclaire-summer-2025-dress-trends.json").exists())
            signal_bundle = _read_json(run_dir / "signal_bundle.json")
            self.assertTrue(
                any(
                    item["signal_id"].startswith("marieclaire-summer-2025-dress-trends-")
                    for item in signal_bundle["signals"]
                )
            )
            canonical_payload = _read_json(run_dir / "canonical_signals.json")
            marieclaire_signal = next(
                item
                for item in canonical_payload["signals"]
                if item["source_id"] == "marieclaire-summer-2025-dress-trends"
            )
            self.assertEqual(
                marieclaire_signal["extraction_provenance"]["adapter_version"],
                "marieclaire_editorial_v1",
            )

    def test_run_public_signal_refresh_does_not_mutate_active_runtime_evidence(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        elements_path = Path("data/mvp/dress/elements.json")
        strategies_path = Path("data/mvp/dress/strategy_templates.json")
        before_elements = elements_path.read_text(encoding="utf-8")
        before_strategies = strategies_path.read_text(encoding="utf-8")

        with TemporaryDirectory() as temp_dir:
            run_public_signal_refresh(
                registry_path=Path("data/refresh/dress/source_registry.json"),
                output_root=Path(temp_dir),
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_fixture_fetcher_by_url(),
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
        self.assertTrue(any(item["source_id"] == "broken-source" and item["stage"] == "fetch" for item in result["errors"]))


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
                "enabled": True,
            },
        ],
    }


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_html() -> str:
    return (_SOURCE_FIXTURE_DIR / "whowhatwear-summer-2025-dress-trends.html").read_text(encoding="utf-8")


def _fixture_fetcher_by_url() -> Callable[[str], str]:
    html_by_url = {
        "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends": _fixture_html(),
        "https://www.marieclaire.com/fashion/summer-fashion/summer-2025-dress-trends/": (
            _SOURCE_FIXTURE_DIR / "marieclaire-summer-2025-dress-trends.html"
        ).read_text(encoding="utf-8"),
    }

    def fetcher(url: str) -> str:
        return html_by_url[url]

    return fetcher

