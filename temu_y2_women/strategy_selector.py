from __future__ import annotations

from datetime import date
from typing import Any

from temu_y2_women.models import (
    DateWindow,
    NormalizedRequest,
    SelectedStrategy,
    StrategySelectionResult,
    StrategyTemplate,
)

_BASELINE_WARNING = "No specific strategy matched; using baseline strategy."


def select_strategies(
    request: NormalizedRequest,
    strategies: list[dict[str, Any]],
) -> StrategySelectionResult:
    parsed = tuple(_parse_strategy(item) for item in strategies if item.get("status") == "active")
    matching = [
        strategy
        for strategy in parsed
        if strategy.category == request.category
        and strategy.target_market == request.target_market
        and _matches_launch_window(strategy.date_window, request.target_launch_date)
    ]

    specific = [strategy for strategy in matching if strategy.priority > 1]
    prioritized = sorted(
        specific,
        key=lambda strategy: (
            not _occasion_matches(strategy, request),
            -strategy.priority,
            strategy.strategy_id,
        ),
    )
    if prioritized:
        selected = tuple(
            SelectedStrategy(strategy=strategy, reason=strategy.reason_template)
            for strategy in prioritized[:2]
        )
        return StrategySelectionResult(selected=selected, warnings=())

    baselines = sorted(
        (strategy for strategy in matching if strategy.priority <= 1),
        key=lambda strategy: (-strategy.priority, strategy.strategy_id),
    )
    if baselines:
        return StrategySelectionResult(
            selected=(SelectedStrategy(strategy=baselines[0], reason=baselines[0].reason_template),),
            warnings=(_BASELINE_WARNING,),
        )

    return StrategySelectionResult(selected=(), warnings=(_BASELINE_WARNING,))


def _parse_strategy(payload: dict[str, Any]) -> StrategyTemplate:
    slot_preferences = {
        key: tuple(value)
        for key, value in payload.get("slot_preferences", {}).items()
    }
    return StrategyTemplate(
        strategy_id=payload["strategy_id"],
        category=payload["category"],
        target_market=payload["target_market"],
        priority=int(payload["priority"]),
        date_window=DateWindow(
            start=payload["date_window"]["start"],
            end=payload["date_window"]["end"],
        ),
        occasion_tags=tuple(payload.get("occasion_tags", [])),
        boost_tags=tuple(payload.get("boost_tags", [])),
        suppress_tags=tuple(payload.get("suppress_tags", [])),
        slot_preferences=slot_preferences,
        score_boost=float(payload["score_boost"]),
        score_cap=float(payload["score_cap"]),
        prompt_hints=tuple(payload.get("prompt_hints", [])),
        reason_template=payload["reason_template"],
        status=payload["status"],
    )


def _matches_launch_window(window: DateWindow, launch_date: date) -> bool:
    current = (launch_date.month, launch_date.day)
    start = _parse_month_day(window.start)
    end = _parse_month_day(window.end)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _parse_month_day(value: str) -> tuple[int, int]:
    month_text, day_text = value.split("-", maxsplit=1)
    return int(month_text), int(day_text)


def _occasion_matches(strategy: StrategyTemplate, request: NormalizedRequest) -> bool:
    if not strategy.occasion_tags:
        return False
    return any(tag in strategy.occasion_tags for tag in request.occasion_tags)
