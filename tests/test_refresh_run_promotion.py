from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_PROMOTION_FIXTURE_DIR = Path("tests/fixtures/promotion/dress")


class RefreshRunPromotionPrepareTest(unittest.TestCase):
    def test_prepare_from_refresh_run_writes_default_promotion_review(self) -> None:
        from temu_y2_women.refresh_run_promotion import prepare_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)

            result = prepare_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["schema_version"], "promotion-review-v1")
            self.assertTrue((run_dir / "promotion_review.json").exists())

    def test_prepare_from_refresh_run_rejects_missing_required_artifacts(self) -> None:
        from temu_y2_women.refresh_run_promotion import prepare_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            (run_dir / "refresh_report.json").unlink()
            elements_path, strategies_path = _seed_active_evidence(temp_root)

            result = prepare_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["error"]["code"], "INVALID_REFRESH_RUN")
            self.assertEqual(result["error"]["details"]["field"], "refresh_report.json")


def _seed_refresh_run(temp_root: Path, scenario: str) -> Path:
    run_dir = temp_root / "refresh-run"
    run_dir.mkdir()
    for filename in ("draft_elements.json", "draft_strategy_hints.json"):
        (run_dir / filename).write_text(
            (_PROMOTION_FIXTURE_DIR / scenario / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (run_dir / "ingestion_report.json").write_text(
        json.dumps({"schema_version": "signal-ingestion-v1"}),
        encoding="utf-8",
    )
    (run_dir / "refresh_report.json").write_text(
        json.dumps({"schema_version": "public-signal-refresh-v1"}),
        encoding="utf-8",
    )
    return run_dir


def _seed_active_evidence(temp_root: Path) -> tuple[Path, Path]:
    elements_path = temp_root / "elements.json"
    strategies_path = temp_root / "strategy_templates.json"
    elements_path.write_text(
        (_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    strategies_path.write_text(
        (_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return elements_path, strategies_path
