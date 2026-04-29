from __future__ import annotations

from datetime import date
import unittest

from temu_y2_women.models import (
    ComposedConcept,
    ComposedElement,
    DateWindow,
    NormalizedRequest,
    SelectedStrategy,
    SelectedStyleFamily,
    StyleFamilyProfile,
    StrategyTemplate,
)


class PromptRendererTest(unittest.TestCase):
    def test_render_mode_a_uses_visual_template_and_render_jobs(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_concept(),
            selected_strategies=(_strategy(),),
            selected_style_family=None,
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
            selected_style_family=None,
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
            selected_style_family=None,
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
            selected_style_family=None,
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
            selected_style_family=None,
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

    def test_render_prompt_uses_style_family_specific_shell(self) -> None:
        for case in _style_family_prompt_cases():
            prompt = _render_family_prompt(case["selected_style_family"])
            self.assertIn(case["subject_hint"], prompt)
            self.assertIn(case["scene_hint"], prompt)
            self.assertIn(case["constraint_hint"], prompt)

    def test_render_prompt_omits_print_language_when_concept_has_no_pattern(self) -> None:
        from temu_y2_women.prompt_renderer import render_prompt_bundle

        bundle = render_prompt_bundle(
            request=_request(mode="A"),
            concept=_clean_minimal_concept(),
            selected_strategies=(_strategy(),),
            selected_style_family=_selected_style_family(
                "clean-minimal",
                "quiet minimal studio dress",
                "pared-back tonal studio",
                "even softbox lighting",
                "low-noise product styling",
                ("avoid visible print noise",),
            ),
            warnings=(),
        )

        prompt = bundle["prompt"]
        self.assertNotIn("floral print scale", prompt)
        self.assertNotIn("visible surface print", prompt)
        self.assertNotIn("commercial print scale", prompt)
        self.assertIn("compact poplin fabric", prompt)

    def test_render_prompt_adds_critical_visual_differentiation_for_clean_minimal(self) -> None:
        prompt = _render_family_prompt_with_concept(
            selected_style_family=_selected_style_family(
                "clean-minimal",
                "quiet minimal studio dress",
                "pared-back tonal studio",
                "even softbox lighting",
                "low-noise product styling",
                ("avoid visible print noise",),
            ),
            concept=_clean_minimal_concept(),
        )

        self.assertIn("[关键视觉差异点]", prompt)
        self.assertIn("jewel neckline should read close to the base of the neck", prompt)
        self.assertIn("not a boat neckline", prompt)
        self.assertIn("not a square neckline", prompt)
        self.assertIn("not a sweetheart neckline", prompt)

    def test_render_prompt_adds_critical_visual_differentiation_for_city_polished(self) -> None:
        prompt = _render_family_prompt_with_concept(
            selected_style_family=_selected_style_family(
                "city-polished",
                "structured polished city dress",
                "urban showroom backdrop",
                "clean directional commercial light",
                "sharp commuter-ready styling",
                ("avoid beach props",),
            ),
            concept=_city_polished_concept(),
        )

        self.assertIn("[关键视觉差异点]", prompt)
        self.assertIn("square neckline with visible corner geometry", prompt)
        self.assertIn("tailored seam panel should stay obvious on the front body", prompt)
        self.assertIn("not a boat neckline", prompt)
        self.assertIn("not a sweetheart neckline", prompt)

    def assert_prompt_has_required_blocks(self, prompt: str) -> None:
        self.assertIn("[商品主体]", prompt)
        self.assertIn("[核心结构]", prompt)
        self.assertIn("[关键视觉差异点]", prompt)
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
        style_family=None,
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


def _clean_minimal_concept() -> ComposedConcept:
    return ComposedConcept(
        category="dress",
        concept_score=0.9,
        selected_elements={
            "silhouette": ComposedElement("dress-silhouette-shift-001", "shift"),
            "fabric": ComposedElement("dress-fabric-compact-poplin-001", "compact poplin"),
            "neckline": ComposedElement("dress-neckline-jewel-001", "jewel neckline"),
            "sleeve": ComposedElement("dress-sleeve-cap-001", "cap sleeve"),
            "dress_length": ComposedElement("dress-length-midi-001", "midi"),
            "color_family": ComposedElement("dress-color-stone-001", "stone"),
            "opacity_level": ComposedElement("dress-opacity-level-opaque-001", "opaque"),
        },
        style_summary=("minimal", "quiet", "structured"),
        constraint_notes=(),
    )


def _selected_style_family(
    style_family_id: str,
    subject_hint: str,
    scene_hint: str,
    lighting_hint: str,
    styling_hint: str,
    constraint_hints: tuple[str, ...],
) -> SelectedStyleFamily:
    return SelectedStyleFamily(
        profile=StyleFamilyProfile(
            style_family_id=style_family_id,
            hard_slot_values={},
            soft_slot_values={},
            blocked_slot_values={},
            subject_hint=subject_hint,
            scene_hint=scene_hint,
            lighting_hint=lighting_hint,
            styling_hint=styling_hint,
            constraint_hints=constraint_hints,
            fallback_reason="fixture",
            status="active",
        ),
        selection_mode="explicit",
        reason="fixture",
    )


def _style_family_prompt_cases() -> tuple[dict[str, object], ...]:
    return (
        _style_family_prompt_case(
            "vacation-romantic",
            "airy romantic resort dress",
            "sunlit resort veranda",
            "soft daylight glow",
            "relaxed feminine movement",
            "avoid nightlife mood",
        ),
        _style_family_prompt_case(
            "clean-minimal",
            "quiet minimal studio dress",
            "pared-back tonal studio",
            "even softbox lighting",
            "low-noise product styling",
            "avoid visible print noise",
        ),
        _style_family_prompt_case(
            "city-polished",
            "structured polished city dress",
            "urban showroom backdrop",
            "clean directional commercial light",
            "sharp commuter-ready styling",
            "avoid beach props",
        ),
        _style_family_prompt_case(
            "party-fitted",
            "sleek fitted evening dress",
            "nightlife-inspired dark studio",
            "high-contrast evening light",
            "confident after-dark pose",
            "avoid resort softness",
        ),
    )


def _city_polished_concept() -> ComposedConcept:
    return ComposedConcept(
        category="dress",
        concept_score=0.92,
        selected_elements={
            "silhouette": ComposedElement("dress-silhouette-sheath-001", "sheath"),
            "fabric": ComposedElement("dress-fabric-matte-crepe-001", "matte crepe"),
            "neckline": ComposedElement("dress-neckline-square-001", "square neckline"),
            "sleeve": ComposedElement("dress-sleeve-cap-001", "cap sleeve"),
            "dress_length": ComposedElement("dress-length-midi-001", "midi"),
            "waistline": ComposedElement("dress-waistline-natural-001", "natural waist"),
            "color_family": ComposedElement("dress-color-family-navy-001", "navy"),
            "opacity_level": ComposedElement("dress-opacity-level-opaque-001", "opaque"),
            "detail": ComposedElement("dress-detail-tailored-panel-001", "tailored seam panel"),
        },
        style_summary=("city", "polished", "structured"),
        constraint_notes=(),
    )


def _style_family_prompt_case(
    style_family_id: str,
    subject_hint: str,
    scene_hint: str,
    lighting_hint: str,
    styling_hint: str,
    constraint_hint: str,
) -> dict[str, object]:
    return {
        "subject_hint": subject_hint,
        "scene_hint": scene_hint,
        "constraint_hint": constraint_hint,
        "selected_style_family": _selected_style_family(
            style_family_id,
            subject_hint,
            scene_hint,
            lighting_hint,
            styling_hint,
            (constraint_hint,),
        ),
    }


def _render_family_prompt(selected_style_family: SelectedStyleFamily) -> str:
    return _render_family_prompt_with_concept(selected_style_family, _objective_concept())


def _render_family_prompt_with_concept(
    selected_style_family: SelectedStyleFamily,
    concept: ComposedConcept,
) -> str:
    from temu_y2_women.prompt_renderer import render_prompt_bundle

    return render_prompt_bundle(
        request=_request(mode="A"),
        concept=concept,
        selected_strategies=(_strategy(),),
        selected_style_family=selected_style_family,
        warnings=(),
    )["prompt"]
