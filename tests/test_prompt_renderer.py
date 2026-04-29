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

    def test_render_mode_a_prompt_includes_objective_slots(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_objective_concept(),
            selected_strategies=(_strategy(),),
            warnings=(),
        )

        prompt = bundle["prompt"]
        self.assertIn("mini length", prompt)
        self.assertIn("drop waist", prompt)
        self.assertIn("white color story", prompt)
        self.assertIn("micro print scale", prompt)
        self.assertIn("sheer overlay effect", prompt)
        detail_prompts = {item["prompt_id"]: item["prompt"] for item in bundle["detail_prompts"]}
        self.assertIn("waistline placement", detail_prompts["construction_closeup"])
        self.assertIn("micro print scale", detail_prompts["fabric_print_closeup"])
        self.assertIn("mini proportion", detail_prompts["hem_and_drape_closeup"])

    def test_render_mode_a_derived_hero_jobs_use_edit_instructions(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_objective_concept(),
            selected_strategies=(_strategy(),),
            warnings=(),
        )

        hero_jobs = {item["prompt_id"]: item for item in bundle["render_jobs"] if item["group"] == "hero"}
        self.assertIn("[商品主体]", hero_jobs["hero_front"]["prompt"])
        self.assertTrue(hero_jobs["hero_three_quarter"]["prompt"].startswith("Edit the reference image."))
        self.assertTrue(hero_jobs["hero_back"]["prompt"].startswith("Edit the reference image."))
        self.assertNotIn("[商品主体]", hero_jobs["hero_three_quarter"]["prompt"])
        self.assertNotIn("[商品主体]", hero_jobs["hero_back"]["prompt"])
        self.assertIn("Keep the exact same dress", hero_jobs["hero_three_quarter"]["prompt"])
        self.assertIn("Keep the exact same dress", hero_jobs["hero_back"]["prompt"])
        self.assertIn("Only change the camera angle to a three-quarter view", hero_jobs["hero_three_quarter"]["prompt"])
        self.assertIn("Only change the camera angle to a back view", hero_jobs["hero_back"]["prompt"])

    def test_render_mode_a_detail_jobs_use_edit_instructions(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_objective_concept(),
            selected_strategies=(_strategy(),),
            warnings=(),
        )

        detail_jobs = {item["prompt_id"]: item for item in bundle["render_jobs"] if item["group"] == "detail"}
        construction_prompt = detail_jobs["construction_closeup"]["prompt"]
        fabric_prompt = detail_jobs["fabric_print_closeup"]["prompt"]
        hem_prompt = detail_jobs["hem_and_drape_closeup"]["prompt"]

        self.assertTrue(construction_prompt.startswith("Edit the reference image."))
        self.assertTrue(fabric_prompt.startswith("Edit the reference image."))
        self.assertTrue(hem_prompt.startswith("Edit the reference image."))
        self.assertIn("Keep the exact same dress", construction_prompt)
        self.assertIn("Zoom into the square neckline, neck scarf, and waistline placement", construction_prompt)
        self.assertIn("Keep the exact same dress", fabric_prompt)
        self.assertIn("Zoom into the cotton poplin fabric surface", fabric_prompt)
        self.assertIn("Keep the exact same dress", hem_prompt)
        self.assertIn("Zoom into the lower skirt and hem area", hem_prompt)

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


def _objective_concept() -> ComposedConcept:
    return ComposedConcept(
        category="dress",
        concept_score=0.94,
        selected_elements={
            "silhouette": ComposedElement("dress-silhouette-a-line-001", "a-line"),
            "fabric": ComposedElement("dress-fabric-cotton-poplin-001", "cotton poplin"),
            "neckline": ComposedElement("dress-neckline-square-001", "square neckline"),
            "sleeve": ComposedElement("dress-sleeve-puff-001", "short puff sleeve"),
            "dress_length": ComposedElement("dress-length-mini-001", "mini"),
            "waistline": ComposedElement("dress-waistline-drop-waist-001", "drop waist"),
            "color_family": ComposedElement("dress-color-family-white-001", "white"),
            "pattern": ComposedElement("dress-pattern-polka-dot-001", "polka dot"),
            "print_scale": ComposedElement("dress-print-scale-micro-print-001", "micro print"),
            "opacity_level": ComposedElement("dress-opacity-level-sheer-001", "sheer"),
            "detail": ComposedElement("dress-detail-neck-scarf-001", "neck scarf"),
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
