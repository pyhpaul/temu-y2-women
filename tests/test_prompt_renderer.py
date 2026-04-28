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
    def test_render_mode_a_uses_visual_template_and_render_jobs(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_concept(),
            selected_strategies=(_strategy(),),
            warnings=(),
        )

        self.assertEqual(bundle["mode"], "A")
        self.assertEqual(bundle["template_version"], "visual-prompt-v2")
        self.assert_prompt_has_required_blocks(bundle["prompt"])
        self.assertIn("product-first presentation", bundle["prompt"])
        self.assertIn("on-model ecommerce hero image", bundle["prompt"])
        self.assertNotIn("price band", bundle["prompt"])
        self.assertNotIn("shopper appeal", bundle["prompt"])
        self.assertNotIn("development notes", bundle["prompt"])
        self.assert_render_jobs(bundle)
        self.assert_detail_prompts(bundle["detail_prompts"])

    def test_render_mode_b_uses_development_reference_template_and_render_jobs(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="B"),
            concept=_concept(),
            selected_strategies=(_strategy(),),
            warnings=("keep trims production-friendly",),
        )

        self.assertEqual(bundle["mode"], "B")
        self.assertEqual(bundle["template_version"], "visual-prompt-v2")
        self.assert_prompt_has_required_blocks(bundle["prompt"])
        self.assertIn("development reference image", bundle["prompt"])
        self.assertIn("construction review clarity", " ".join(bundle["render_notes"]))
        self.assertEqual(
            bundle["development_notes"],
            ["summer-ready", "vacation-oriented", "feminine silhouette"],
        )
        self.assertIn("development notes: summer-ready; vacation-oriented; feminine silhouette", bundle["prompt"])
        self.assert_render_jobs(bundle)
        self.assert_detail_prompts(bundle["detail_prompts"])

    def assert_prompt_has_required_blocks(self, prompt: str) -> None:
        self.assertIn("[商品主体]", prompt)
        self.assertIn("[核心结构]", prompt)
        self.assertIn("[生产与细节展示要求]", prompt)
        self.assertIn("[镜头与构图]", prompt)
        self.assertIn("[面料与工艺表现]", prompt)
        self.assertIn("[场景与光线]", prompt)
        self.assertIn("[约束与避免项]", prompt)

    def assert_detail_prompts(self, detail_prompts: object) -> None:
        self.assertIsInstance(detail_prompts, list)
        prompt_ids = {item["prompt_id"] for item in detail_prompts}
        self.assertEqual(
            prompt_ids,
            {"construction_closeup", "fabric_print_closeup", "hem_and_drape_closeup"},
        )
        for item in detail_prompts:
            self.assertIn("prompt", item)
            self.assertTrue(item["prompt"].strip())
            self.assertEqual(item["render_strategy"], "edit")
            self.assertEqual(item["reference_prompt_id"], "hero_front")

    def assert_render_jobs(self, bundle: dict[str, object]) -> None:
        render_jobs = bundle["render_jobs"]
        self.assertIsInstance(render_jobs, list)
        self.assertEqual(
            [(item["prompt_id"], item["group"], item["output_name"]) for item in render_jobs],
            [
                ("hero_front", "hero", "hero_front.png"),
                ("hero_three_quarter", "hero", "hero_three_quarter.png"),
                ("hero_back", "hero", "hero_back.png"),
                ("construction_closeup", "detail", "construction_closeup.png"),
                ("fabric_print_closeup", "detail", "fabric_print_closeup.png"),
                ("hem_and_drape_closeup", "detail", "hem_and_drape_closeup.png"),
            ],
        )
        self.assertEqual(bundle["prompt"], render_jobs[0]["prompt"])
        detail_prompts = {item["prompt_id"]: item["prompt"] for item in bundle["detail_prompts"]}
        for index, item in enumerate(render_jobs):
            self.assertTrue(item["prompt"].strip())
            if index == 0:
                self.assertEqual(item["render_strategy"], "generate")
                self.assertIsNone(item["reference_prompt_id"])
            else:
                self.assertEqual(item["render_strategy"], "edit")
                self.assertEqual(item["reference_prompt_id"], "hero_front")
            if item["group"] == "detail":
                self.assertEqual(detail_prompts[item["prompt_id"]], item["prompt"])


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
