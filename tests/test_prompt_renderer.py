from __future__ import annotations

from datetime import date
import unittest

from temu_y2_women.models import (
    ComposedConcept,
    ComposedElement,
    DateWindow,
    NormalizedRequest,
    SelectedStrategy,
    StrategyTemplate,
)


class PromptRendererTest(unittest.TestCase):
    def test_render_mode_a_uses_five_block_structure_and_product_appeal(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_concept(),
            selected_strategies=(_strategy(),),
            warnings=(),
        )

        self.assertEqual(bundle["mode"], "A")
        self.assert_prompt_has_required_blocks(bundle["prompt"])
        self.assertIn("product appeal", " ".join(bundle["render_notes"]))
        self.assertIn("hero ecommerce concept image", bundle["prompt"])
        self.assertIn("shopper appeal", bundle["prompt"])
        self.assertNotIn("development notes", bundle["prompt"])

    def test_render_mode_b_uses_five_block_structure_and_development_notes(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="B"),
            concept=_concept(),
            selected_strategies=(_strategy(),),
            warnings=("keep trims production-friendly",),
        )

        self.assertEqual(bundle["mode"], "B")
        self.assert_prompt_has_required_blocks(bundle["prompt"])
        self.assertIn("development reference image", bundle["prompt"])
        self.assertIn("garment construction clarity", " ".join(bundle["render_notes"]))
        self.assertEqual(
            bundle["development_notes"],
            ["summer-ready", "vacation-oriented", "feminine silhouette"],
        )
        self.assertIn("development notes: summer-ready; vacation-oriented; feminine silhouette", bundle["prompt"])

    def assert_prompt_has_required_blocks(self, prompt: str) -> None:
        self.assertIn("[商品主体]", prompt)
        self.assertIn("[核心结构]", prompt)
        self.assertIn("[风格与时效]", prompt)
        self.assertIn("[展示方式]", prompt)
        self.assertIn("[约束与避免项]", prompt)


def _request(mode: str) -> NormalizedRequest:
    return NormalizedRequest(
        category="dress",
        target_market="US",
        target_launch_date=date(2026, 6, 15),
        mode=mode,
        price_band="mid",
        occasion_tags=("vacation",),
        must_have_tags=("floral",),
        avoid_tags=("bodycon",),
    )


def _concept() -> ComposedConcept:
    return ComposedConcept(
        category="dress",
        concept_score=0.91,
        selected_elements={
            "silhouette": ComposedElement("dress-silhouette-a-line-001", "a-line"),
            "fabric": ComposedElement("dress-fabric-cotton-poplin-001", "cotton poplin"),
            "neckline": ComposedElement("dress-neckline-square-001", "square neckline"),
            "sleeve": ComposedElement("dress-sleeve-puff-001", "short puff sleeve"),
            "pattern": ComposedElement("dress-pattern-floral-001", "floral print"),
        },
        style_summary=("summer-ready", "vacation-oriented", "feminine silhouette"),
        constraint_notes=("must_have_tags satisfied: floral",),
    )


def _strategy() -> SelectedStrategy:
    return SelectedStrategy(
        strategy=StrategyTemplate(
            strategy_id="dress-us-summer-vacation",
            category="dress",
            target_market="US",
            priority=10,
            date_window=DateWindow(start="05-15", end="08-31"),
            occasion_tags=("vacation",),
            boost_tags=("summer", "floral"),
            suppress_tags=("velvet",),
            slot_preferences={"silhouette": ("a-line",)},
            score_boost=0.12,
            score_cap=0.2,
            prompt_hints=("fresh summer styling", "vacation-ready feminine silhouette"),
            reason_template="launch date falls into the US summer vacation window",
            status="active",
        ),
        reason="matched summer vacation window",
    )
