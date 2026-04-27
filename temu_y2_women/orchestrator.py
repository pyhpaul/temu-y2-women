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
from temu_y2_women.strategy_selector import select_strategies


def generate_dress_concept(
    payload: dict[str, Any],
    evidence_paths: EvidencePaths | None = None,
) -> dict[str, Any]:
    try:
        resolved_paths = evidence_paths or EvidencePaths.defaults()
        request = normalize_request(payload)
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
        grouped_candidates, retrieval_warnings = retrieve_candidates(request, elements, strategy_result.selected)
        concept = compose_concept(request, grouped_candidates)
        prompt_bundle = render_prompt_bundle(
            request=request,
            concept=concept,
            selected_strategies=strategy_result.selected,
            warnings=strategy_result.warnings + retrieval_warnings,
        )
        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=strategy_result.selected,
        )
        return package_success_result(
            request=request,
            selected_strategies=strategy_result.selected,
            retrieved_elements=flatten_candidates(grouped_candidates),
            composed_concept=concept,
            prompt_bundle=prompt_bundle,
            factory_spec=factory_spec,
            warnings=strategy_result.warnings + retrieval_warnings,
        )
    except GenerationError as error:
        return error.to_dict()
