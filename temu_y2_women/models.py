from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class NormalizedRequest:
    category: str
    target_market: str
    target_launch_date: date
    mode: str
    price_band: str | None
    occasion_tags: tuple[str, ...]
    must_have_tags: tuple[str, ...]
    avoid_tags: tuple[str, ...]
    style_family: str | None = None


@dataclass(frozen=True, slots=True)
class DateWindow:
    start: str
    end: str


@dataclass(frozen=True, slots=True)
class StrategyTemplate:
    strategy_id: str
    category: str
    target_market: str
    priority: int
    date_window: DateWindow
    occasion_tags: tuple[str, ...]
    boost_tags: tuple[str, ...]
    suppress_tags: tuple[str, ...]
    slot_preferences: dict[str, tuple[str, ...]]
    score_boost: float
    score_cap: float
    prompt_hints: tuple[str, ...]
    reason_template: str
    status: str


@dataclass(frozen=True, slots=True)
class SelectedStrategy:
    strategy: StrategyTemplate
    reason: str


@dataclass(frozen=True, slots=True)
class StrategySelectionResult:
    selected: tuple[SelectedStrategy, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StyleFamilyProfile:
    style_family_id: str
    hard_slot_values: dict[str, tuple[str, ...]]
    soft_slot_values: dict[str, tuple[str, ...]]
    blocked_slot_values: dict[str, tuple[str, ...]]
    subject_hint: str
    scene_hint: str
    lighting_hint: str
    styling_hint: str
    constraint_hints: tuple[str, ...]
    fallback_reason: str
    status: str


@dataclass(frozen=True, slots=True)
class SelectedStyleFamily:
    profile: StyleFamilyProfile
    selection_mode: str
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateElement:
    element_id: str
    category: str
    slot: str
    value: str
    tags: tuple[str, ...]
    base_score: float
    effective_score: float
    risk_flags: tuple[str, ...]
    evidence_summary: str


@dataclass(frozen=True, slots=True)
class ComposedElement:
    element_id: str
    value: str


@dataclass(frozen=True, slots=True)
class ComposedConcept:
    category: str
    concept_score: float
    selected_elements: dict[str, ComposedElement]
    style_summary: tuple[str, ...]
    constraint_notes: tuple[str, ...]
