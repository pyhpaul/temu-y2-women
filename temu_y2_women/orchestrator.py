from __future__ import annotations

from typing import Any

from temu_y2_women.composition_engine import compose_concept
from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.evidence_repository import (
    flatten_candidates,
    load_elements,
    load_strategy_templates,
    retrieve_candidates,
)
from temu_y2_women.errors import GenerationError
from temu_y2_women.factory_spec_builder import build_factory_spec
from temu_y2_women.prompt_renderer import render_prompt_bundle
from temu_y2_women.request_normalizer import normalize_request
from temu_y2_women.result_packager import package_success_result
from temu_y2_women.style_family_repository import load_style_families
from temu_y2_women.style_family_selector import select_style_family
from temu_y2_women.strategy_selector import select_strategies


def generate_dress_concept(
    payload: dict[str, Any],
    evidence_paths: EvidencePaths | None = None,
) -> dict[str, Any]:
    try:
        resolved_paths = evidence_paths or EvidencePaths.defaults()
        request = normalize_request(payload)
        style_families = load_style_families(
            path=resolved_paths.style_families_path or EvidencePaths.defaults().style_families_path,
            elements_path=resolved_paths.elements_path,
            taxonomy_path=resolved_paths.taxonomy_path,
        )
        selected_style_family = select_style_family(request, style_families)
        strategies = load_strategy_templates(
            path=resolved_paths.strategies_path,
            taxonomy_path=resolved_paths.taxonomy_path,
            elements_path=resolved_paths.elements_path,
        )
        strategy_result = select_strategies(request, strategies)
        elements = load_elements(
            path=resolved_paths.elements_path,
            taxonomy_path=resolved_paths.taxonomy_path,
        )
        grouped_candidates, retrieval_warnings = retrieve_candidates(
            request,
            elements,
            strategy_result.selected,
            selected_style_family=selected_style_family,
        )
        concept = _compose_or_raise_no_candidates(request, grouped_candidates)
        prompt_bundle = render_prompt_bundle(
            request=request,
            concept=concept,
            selected_strategies=strategy_result.selected,
            selected_style_family=selected_style_family,
            warnings=strategy_result.warnings + retrieval_warnings,
        )
        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=strategy_result.selected,
            selected_style_family=selected_style_family,
        )
        return package_success_result(
            request=request,
            selected_strategies=strategy_result.selected,
            selected_style_family=selected_style_family,
            retrieved_elements=flatten_candidates(grouped_candidates),
            composed_concept=concept,
            prompt_bundle=prompt_bundle,
            factory_spec=factory_spec,
            warnings=strategy_result.warnings + retrieval_warnings,
        )
    except GenerationError as error:
        return error.to_dict()


def _compose_or_raise_no_candidates(
    request: dict[str, Any] | Any,
    grouped_candidates: dict[str, list[dict[str, Any]]],
):
    try:
        return compose_concept(request, grouped_candidates)
    except GenerationError as error:
        if error.code != "INCOMPLETE_CONCEPT":
            raise
        raise GenerationError(
            code="NO_CANDIDATES",
            message="no eligible dress elements found after filtering",
            details={"category": request.category, "avoid_tags": list(request.avoid_tags)},
        ) from error
