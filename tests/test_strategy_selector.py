from datetime import date
import unittest

from temu_y2_women.models import NormalizedRequest


class StrategySelectorTest(unittest.TestCase):
    def test_select_matching_seasonal_strategy(self) -> None:
        from temu_y2_women.strategy_selector import select_strategies

        request = _request(launch_date=date(2026, 6, 15), occasion_tags=("vacation",))
        strategies = [
            {
                "strategy_id": "baseline-dress-us",
                "category": "dress",
                "target_market": "US",
                "priority": 1,
                "date_window": {"start": "01-01", "end": "12-31"},
                "occasion_tags": [],
                "boost_tags": ["dress"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.02,
                "score_cap": 0.05,
                "prompt_hints": ["baseline dress styling"],
                "reason_template": "baseline fallback for dress requests",
                "status": "active",
            },
            {
                "strategy_id": "summer-vacation-dress",
                "category": "dress",
                "target_market": "US",
                "priority": 10,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": ["vacation", "casual"],
                "boost_tags": ["summer", "floral"],
                "suppress_tags": ["heavy"],
                "slot_preferences": {"pattern": ["floral"]},
                "score_boost": 0.12,
                "score_cap": 0.2,
                "prompt_hints": ["summer vacation mood"],
                "reason_template": "launch date falls into the US summer vacation window",
                "status": "active",
            },
        ]

        result = select_strategies(request, strategies)

        self.assertEqual([item.strategy.strategy_id for item in result.selected], ["summer-vacation-dress"])
        self.assertEqual(result.warnings, ())

    def test_prefer_occasion_aligned_strategy(self) -> None:
        from temu_y2_women.strategy_selector import select_strategies

        request = _request(launch_date=date(2026, 7, 4), occasion_tags=("party",))
        strategies = [
            {
                "strategy_id": "summer-casual-dress",
                "category": "dress",
                "target_market": "US",
                "priority": 10,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": ["casual"],
                "boost_tags": ["summer"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.1,
                "score_cap": 0.2,
                "prompt_hints": ["casual summer mood"],
                "reason_template": "summer casual window",
                "status": "active",
            },
            {
                "strategy_id": "summer-party-dress",
                "category": "dress",
                "target_market": "US",
                "priority": 8,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": ["party"],
                "boost_tags": ["party"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.11,
                "score_cap": 0.2,
                "prompt_hints": ["party summer mood"],
                "reason_template": "summer party window",
                "status": "active",
            },
        ]

        result = select_strategies(request, strategies)

        self.assertEqual(result.selected[0].strategy.strategy_id, "summer-party-dress")

    def test_ignore_specific_strategy_when_occasion_is_mismatched(self) -> None:
        from temu_y2_women.strategy_selector import select_strategies

        request = _request(launch_date=date(2026, 7, 4), occasion_tags=("party",))
        strategies = [
            {
                "strategy_id": "baseline-dress-us",
                "category": "dress",
                "target_market": "US",
                "priority": 1,
                "date_window": {"start": "01-01", "end": "12-31"},
                "occasion_tags": [],
                "boost_tags": ["dress"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.02,
                "score_cap": 0.05,
                "prompt_hints": ["baseline dress styling"],
                "reason_template": "baseline fallback for dress requests",
                "status": "active",
            },
            {
                "strategy_id": "summer-vacation-dress",
                "category": "dress",
                "target_market": "US",
                "priority": 10,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": ["vacation", "resort"],
                "boost_tags": ["summer", "floral"],
                "suppress_tags": ["heavy"],
                "slot_preferences": {"pattern": ["floral"]},
                "score_boost": 0.12,
                "score_cap": 0.2,
                "prompt_hints": ["summer vacation mood"],
                "reason_template": "launch date falls into the US summer vacation window",
                "status": "active",
            },
        ]

        result = select_strategies(request, strategies)

        self.assertEqual([item.strategy.strategy_id for item in result.selected], ["baseline-dress-us"])
        self.assertEqual(result.warnings, ("No specific strategy matched; using baseline strategy.",))

    def test_fall_back_to_baseline_strategy(self) -> None:
        from temu_y2_women.strategy_selector import select_strategies

        request = _request(launch_date=date(2026, 1, 10))
        strategies = [
            {
                "strategy_id": "baseline-dress-us",
                "category": "dress",
                "target_market": "US",
                "priority": 1,
                "date_window": {"start": "01-01", "end": "12-31"},
                "occasion_tags": [],
                "boost_tags": ["dress"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.02,
                "score_cap": 0.05,
                "prompt_hints": ["baseline dress styling"],
                "reason_template": "baseline fallback for dress requests",
                "status": "active",
            }
        ]

        result = select_strategies(request, strategies)

        self.assertEqual(result.selected[0].strategy.strategy_id, "baseline-dress-us")
        self.assertEqual(
            result.warnings,
            ("No specific strategy matched; using baseline strategy.",),
        )

    def test_select_up_to_two_strategies_and_merge_equally(self) -> None:
        from temu_y2_women.strategy_selector import select_strategies

        request = _request(launch_date=date(2026, 7, 4), occasion_tags=("vacation",))
        strategies = [
            {
                "strategy_id": "summer-vacation-dress",
                "category": "dress",
                "target_market": "US",
                "priority": 10,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": ["vacation"],
                "boost_tags": ["summer", "vacation"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.12,
                "score_cap": 0.2,
                "prompt_hints": ["vacation mood"],
                "reason_template": "vacation window",
                "status": "active",
            },
            {
                "strategy_id": "summer-floral-dress",
                "category": "dress",
                "target_market": "US",
                "priority": 9,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": [],
                "boost_tags": ["floral"],
                "suppress_tags": [],
                "slot_preferences": {},
                "score_boost": 0.08,
                "score_cap": 0.1,
                "prompt_hints": ["floral direction"],
                "reason_template": "summer floral window",
                "status": "active",
            },
        ]

        result = select_strategies(request, strategies)

        self.assertEqual(
            [item.strategy.strategy_id for item in result.selected],
            ["summer-vacation-dress", "summer-floral-dress"],
        )

    def test_selects_product_image_overlay_alongside_primary_strategy(self) -> None:
        from temu_y2_women.strategy_selector import select_strategies

        request = _request(launch_date=date(2026, 7, 4), occasion_tags=("vacation",))
        strategies = [
            {
                "strategy_id": "dress-us-summer-vacation",
                "category": "dress",
                "target_market": "US",
                "priority": 10,
                "date_window": {"start": "05-15", "end": "08-31"},
                "occasion_tags": ["vacation", "resort"],
                "boost_tags": ["summer", "vacation"],
                "suppress_tags": [],
                "slot_preferences": {"detail": ["neck scarf"]},
                "score_boost": 0.12,
                "score_cap": 0.2,
                "prompt_hints": ["vacation mood"],
                "reason_template": "summer vacation window",
                "status": "active",
            },
            {
                "strategy_id": "dress-us-summer-vacation-product-image",
                "category": "dress",
                "target_market": "US",
                "priority": 1,
                "date_window": {"start": "01-01", "end": "12-31"},
                "occasion_tags": ["vacation"],
                "boost_tags": ["summer", "vacation", "feminine"],
                "suppress_tags": [],
                "slot_preferences": {"detail": ["waist tie"]},
                "score_boost": 0.08,
                "score_cap": 0.12,
                "prompt_hints": ["product image overlay"],
                "reason_template": "product image evidence overlay",
                "status": "active",
            },
        ]

        result = select_strategies(request, strategies)

        self.assertEqual(
            [item.strategy.strategy_id for item in result.selected],
            ["dress-us-summer-vacation", "dress-us-summer-vacation-product-image"],
        )


def _request(
    launch_date: date,
    occasion_tags: tuple[str, ...] = (),
) -> NormalizedRequest:
    return NormalizedRequest(
        category="dress",
        target_market="US",
        target_launch_date=launch_date,
        mode="A",
        price_band=None,
        occasion_tags=occasion_tags,
        must_have_tags=(),
        avoid_tags=(),
    )
